"""
Services métier du module Supervision.

Phase S1 : AuditService, utilisé par toutes les actions administratives.
Phase S2 : UserSupervisionService (suspension / réactivation de comptes).
Phase S3 : EventSupervisionService (annulation) et CategorySupervisionService.

Les services de supervision ne refont PAS la logique métier des autres
modules : ils appellent EventService / CategoryService (module events)
et y ajoutent le verrouillage, la raison et la trace d'audit.

Règle d'usage : chaque service d'action appelle AuditService.log() DANS
SA transaction (transaction.atomic). Ainsi, soit l'action ET sa trace
sont enregistrées, soit aucune des deux : jamais d'action sans trace.
"""

import logging
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

# ... le reste des imports existants

from apps.accounts.models import User
from apps.events.models import Category, Event
from apps.events.services import CategoryService, EventService
from apps.registrations.constants import RegistrationStatus
from common.exceptions.business import CategoryAlreadyExists
from apps.supervision.constants import (
    FILTERED_VALUE,
    SENSITIVE_EXACT_KEYS,
    SENSITIVE_KEY_FRAGMENTS,
    USER_AGENT_MAX_LENGTH,
    AuditAction,
    AuditEntity,
    AuditResult,
)
from apps.supervision.exceptions import (
    ActorNoLongerAdmin,
    CategoryAlreadyActive,
    CategoryAlreadyInactive,
    SecurityGuardDenied,
    SupervisionCategoryNotFound,
    SupervisionEventNotFound,
    SupervisionUserNotFound,
    UserAlreadyActive,
    UserAlreadySuspended,
)
from apps.supervision.models import AuditLog
from apps.supervision.validators import (
    ensure_can_change_account_status,
    ensure_not_last_active_admin,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Nettoyage des métadonnées
# ------------------------------------------------------------------
def _is_sensitive_key(key) -> bool:
    name = str(key).lower()
    return name in SENSITIVE_EXACT_KEYS or any(f in name for f in SENSITIVE_KEY_FRAGMENTS)


def sanitize_metadata(value):
    """
    Remplace par « [FILTRÉ] » toute valeur dont la clé semble sensible
    (mot de passe, jeton, secret, carte...), à toutes les profondeurs
    du dictionnaire. Un secret ne doit JAMAIS atteindre la base d'audit.
    """
    if isinstance(value, dict):
        return {
            key: FILTERED_VALUE if _is_sensitive_key(key) else sanitize_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_metadata(item) for item in value]
    return value


# ------------------------------------------------------------------
# Contexte réseau de la requête
# ------------------------------------------------------------------
def get_client_ip(request):
    """
    Adresse IP de la requête.

    On utilise REMOTE_ADDR et PAS l'en-tête X-Forwarded-For : ce dernier
    est fourni par le client et peut être falsifié. Si l'application est
    un jour derrière un proxy de confiance (Nginx), il faudra le
    configurer explicitement.
    """
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


def get_user_agent(request) -> str:
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:USER_AGENT_MAX_LENGTH]


# ------------------------------------------------------------------
# Service d'audit
# ------------------------------------------------------------------
class AuditService:
    """Écriture dans le journal d'audit (le seul point d'entrée)."""

    @staticmethod
    def log(
        *,
        actor,
        action: str,
        entity_type: str,
        entity_id="",
        description: str,
        reason: str = "",
        metadata: dict | None = None,
        result: str = AuditResult.SUCCESS,
        request=None,
    ) -> AuditLog:
        """
        Enregistre une entrée d'audit.

        Args:
            actor: l'utilisateur qui agit (request.user).
            action / entity_type: valeurs de AuditAction / AuditEntity.
            entity_id: identifiant de la ressource visée.
            description: phrase lisible (« Suspension de awa@test.com »).
            reason: raison saisie par l'administrateur.
            metadata: détails complémentaires (nettoyés automatiquement).
            result: SUCCESS ou DENIED.
            request: requête HTTP, pour l'IP et le navigateur.
        """
        entry = AuditLog.objects.create(
            actor=actor if getattr(actor, "pk", None) else None,
            actor_email=getattr(actor, "email", "") or "",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ""),
            description=description,
            reason=reason or "",
            metadata=sanitize_metadata(metadata or {}),
            result=result,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        # Journal technique : identifiants uniquement, pas de contenu.
        logger.info(
            "Audit | action=%s | entity=%s:%s | actor=%s | result=%s",
            action, entity_type, entity_id, getattr(actor, "pk", None), result,
        )
        return entry


# ------------------------------------------------------------------
# Jetons JWT
# ------------------------------------------------------------------
def blacklist_user_tokens(user) -> int:
    """
    Met sur liste noire tous les refresh tokens encore valides du compte.
    Renvoie le nombre de jetons révoqués.

    Pourquoi ? Un refresh token permet d'obtenir de nouveaux access tokens
    pendant 7 jours. Sans cette révocation, un compte suspendu garderait
    une « clé de secours ». (L'access token en cours, lui, est refusé dès
    la requête suivante car SimpleJWT vérifie is_active à chaque appel.)
    """
    tokens = OutstandingToken.objects.filter(
        user=user,
        expires_at__gt=timezone.now(),
        blacklistedtoken__isnull=True,
    )
    created = BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in tokens],
        ignore_conflicts=True,
    )
    return len(created)


# ------------------------------------------------------------------
# Service : comptes utilisateurs
# ------------------------------------------------------------------
class UserSupervisionService:
    """
    Suspension et réactivation des comptes.

    Déroulement d'une action :
        1. verrouiller l'auteur et la cible (select_for_update) ;
        2. vérifier les garde-fous sur des données FRAÎCHES ;
        3. modifier le compte + écrire l'audit, dans la MÊME transaction ;
        4. si un garde-fou refuse : rien n'est modifié, le refus est
           journalisé (DENIED) APRÈS la transaction, puis l'erreur est levée.
    """

    # --- outils internes ------------------------------------------------
    @staticmethod
    def _lock_actor_and_target(actor, user_id):
        """
        Verrouille les deux lignes, toujours dans le même ordre (par id),
        pour éviter un interblocage si deux admins agissent en même temps.
        """
        try:
            target_id = uuid.UUID(str(user_id))
        except ValueError:
            raise SupervisionUserNotFound()

        rows = {
            row.pk: row
            for row in User.objects.select_for_update()
            .filter(pk__in=[actor.pk, target_id])
            .order_by("pk")
        }
        target = rows.get(target_id)
        if target is None:
            raise SupervisionUserNotFound()
        locked_actor = rows.get(actor.pk)
        if locked_actor is None:
            raise ActorNoLongerAdmin()
        return locked_actor, target

    @staticmethod
    def _log_denied(*, actor, action, target, reason, error, request):
        AuditService.log(
            actor=actor,
            action=action,
            entity_type=AuditEntity.USER,
            entity_id=target.pk,
            description=f"Tentative refusée : {AuditAction(action).label.lower()} de {target.email}",
            reason=reason,
            metadata={"denial_code": error.default_code},
            result=AuditResult.DENIED,
            request=request,
        )

        # ⚠️ NOUVEAU : notifier l'utilisateur suspendu
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=target,
                    title="Votre compte a été suspendu",
                    message=(
                        "Votre compte EVENTFLOW a été suspendu par un administrateur. "
                        "Contactez le support pour plus d'informations."
                    ),
                    notification_type=NotificationType.SYSTEM,
                    related_entity_type="user",
                    related_entity_id=str(target.id),
                )
        except Exception as e:
            logger.warning("Notification failed on user suspend | err=%s", e)

    # ------------------------------------------------------------------
    # Helper : envoi d'e-mail à l'organisateur
    # ------------------------------------------------------------------
    @staticmethod
    def _send_account_status_email(
        *,
        target,
        actor,
        action: str,       # "suspend" | "activate"
        reason: str,
    ) -> None:
        """
        Envoie un e-mail à l'organisateur concerné, à l'initiative de
        l'administrateur (`actor`). L'adresse de l'admin est utilisée
        en `reply_to`, et l'en-tête `From` reste `DEFAULT_FROM_EMAIL`
        (recommandation anti-spoofing).
        """
        if not target.email:
            logger.warning("No email to notify | user=%s", getattr(target, "pk", None))
            return

        actor_email = getattr(actor, "email", None) or settings.DEFAULT_FROM_EMAIL
        actor_name = ""
        if actor is not None:
            actor_name = (
                f"{getattr(actor, 'first_name', '')} {getattr(actor, 'last_name', '')}"
            ).strip()

        is_suspend = action == "suspend"
        subject = (
            "Votre compte EVENTFLOW a été suspendu"
            if is_suspend
            else "Votre compte EVENTFLOW a été réactivé"
        )

        context = {
            "first_name": target.first_name or target.email,
            "action_label": "suspendu" if is_suspend else "réactivé",
            "reason": reason or "",
            "actor_email": actor_email,
            "actor_name": actor_name or actor_email,
            "current_year": timezone.now().year,
        }

        # Templates HTML + TXT (à créer si absents, un fallback texte suffit)
        try:
            text_body = render_to_string(
                "emails/account_suspended.txt" if is_suspend else "emails/account_activated.txt",
                context,
            )
            html_body = render_to_string(
                "emails/account_suspended.html" if is_suspend else "emails/account_activated.html",
                context,
            )
        except Exception:
            # Si les templates n'existent pas encore, on utilise un texte simple.
            text_body = (
                f"Bonjour {context['first_name']},\n\n"
                f"Votre compte EVENTFLOW a été {context['action_label']}.\n"
                f"Motif : {context['reason'] or 'Non précisé'}\n\n"
                f"Contact : {actor_email}\n\n"
                f"— EVENTFLOW"
            )
            html_body = None

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[target.email],
            reply_to=[actor_email],
            headers={
                "X-Eventflow-Action": action,
                "X-Eventflow-Admin": actor_email,
            },
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")

        try:
            msg.send(fail_silently=False)
            logger.info(
                "Account status email sent | action=%s | user=%s | admin=%s",
                action, target.pk, actor_email,
            )
        except Exception as exc:  # ne jamais faire échouer l'action métier
            logger.warning(
                "Account status email failed | action=%s | user=%s | err=%s",
                action, target.pk, exc,
            )

    # --- actions ---------------------------------------------------------
    @classmethod
    def suspend(cls, *, actor, user_id, reason: str, request=None) -> User:
        """Suspend un compte : plus de connexion, jetons révoqués, trace d'audit."""
        denial = None
        with transaction.atomic():
            locked_actor, target = cls._lock_actor_and_target(actor, user_id)
            try:
                ensure_can_change_account_status(locked_actor, target)
                ensure_not_last_active_admin(target)
            except SecurityGuardDenied as error:
                denial = error
            else:
                if not target.is_active:
                    raise UserAlreadySuspended()
                target.is_active = False
                target.save(update_fields=["is_active", "updated_at"])
                revoked = blacklist_user_tokens(target)
                AuditService.log(
                    actor=actor,
                    action=AuditAction.USER_SUSPENDED,
                    entity_type=AuditEntity.USER,
                    entity_id=target.pk,
                    description=f"Suspension du compte {target.email}",
                    reason=reason,
                    metadata={"target_email": target.email, "revoked_refresh_tokens": revoked},
                    request=request,
                )

                # ✅ Notification par e-mail de l'organisateur concerné
                cls._send_account_status_email(
                    target=target,
                    actor=actor,
                    action="suspend",
                    reason=reason,
                )

                # ⚠️ NOUVEAU : notifier l'utilisateur réactivé
                try:
                    with transaction.atomic():
                        from apps.notifications.constants import NotificationType
                        from apps.notifications.services import NotificationService
                        NotificationService.create_notification(
                            user=target,
                            title="Votre compte a été réactivé",
                            message=(
                                "Votre compte EVENTFLOW a été réactivé. "
                                "Vous pouvez vous reconnecter."
                            ),
                            notification_type=NotificationType.SYSTEM,
                            related_entity_type="user",
                            related_entity_id=str(target.id),
                        )
                except Exception as e:
                    logger.warning("Notification failed on user activate | err=%s", e)

        if denial is not None:
            cls._log_denied(
                actor=actor, action=AuditAction.USER_SUSPENDED, target=target,
                reason=reason, error=denial, request=request,
            )
            raise denial
        return target

    @classmethod
    def activate(cls, *, actor, user_id, reason: str, request=None) -> User:
        """Réactive un compte suspendu (l'utilisateur devra se reconnecter)."""
        denial = None
        with transaction.atomic():
            locked_actor, target = cls._lock_actor_and_target(actor, user_id)
            try:
                ensure_can_change_account_status(locked_actor, target)
            except SecurityGuardDenied as error:
                denial = error
            else:
                if target.is_active:
                    raise UserAlreadyActive()
                target.is_active = True
                target.save(update_fields=["is_active", "updated_at"])
                AuditService.log(
                    actor=actor,
                    action=AuditAction.USER_ACTIVATED,
                    entity_type=AuditEntity.USER,
                    entity_id=target.pk,
                    description=f"Réactivation du compte {target.email}",
                    reason=reason,
                    metadata={"target_email": target.email},
                    request=request,
                )

                # ✅ Notification par e-mail de l'organisateur concerné
                cls._send_account_status_email(
                    target=target,
                    actor=actor,
                    action="activate",
                    reason=reason,
                )

                # ⚠️ NOUVEAU : notifier l'utilisateur réactivé
                try:
                    with transaction.atomic():
                        from apps.notifications.constants import NotificationType
                        from apps.notifications.services import NotificationService
                        NotificationService.create_notification(
                            user=target,
                            title="Votre compte a été réactivé",
                            message=(
                                "Votre compte EVENTFLOW a été réactivé. "
                                "Vous pouvez vous reconnecter."
                            ),
                            notification_type=NotificationType.SYSTEM,
                            related_entity_type="user",
                            related_entity_id=str(target.id),
                        )
                except Exception as e:
                    logger.warning("Notification failed on user activate | err=%s", e)

        if denial is not None:
            cls._log_denied(
                actor=actor, action=AuditAction.USER_ACTIVATED, target=target,
                reason=reason, error=denial, request=request,
            )
            raise denial
        return target


# ------------------------------------------------------------------
# Service : événements (phase S3)
# ------------------------------------------------------------------
class EventSupervisionService:
    """Modération des événements : l'administrateur peut seulement ANNULER."""

    @staticmethod
    def cancel(*, actor, event_id, reason: str, request=None) -> Event:
        """
        Annule un événement (brouillon ou publié) pour raison de modération.

        Les règles de transition (déjà annulé → 409, terminé → 400) sont
        celles d'EventService : on ne les réécrit pas ici.
        """
        with transaction.atomic():
            event = (
                Event.objects.select_for_update(of=("self",))
                .select_related("organizer")
                .filter(pk=event_id)
                .first()
            )
            if event is None:
                raise SupervisionEventNotFound()

            previous_status = event.status
            EventService.cancel_event(event=event)

            AuditService.log(
                actor=actor,
                action=AuditAction.EVENT_CANCELLED,
                entity_type=AuditEntity.EVENT,
                entity_id=event.pk,
                description=f"Annulation de l'événement « {event.title} »",
                reason=reason,
                metadata={
                    "previous_status": previous_status,
                    "organizer_email": event.organizer.email,
                    "confirmed_registrations": event.registrations.filter(
                        status=RegistrationStatus.CONFIRMED,
                    ).count(),
                },
                request=request,
            )
        return event


# ------------------------------------------------------------------
# Service : catégories (phase S3)
# ------------------------------------------------------------------
class CategorySupervisionService:
    """Gestion des catégories, chaque action étant tracée."""

    @staticmethod
    def _lock(category_id) -> Category:
        category = Category.objects.select_for_update().filter(pk=category_id).first()
        if category is None:
            raise SupervisionCategoryNotFound()
        return category

    @staticmethod
    def _slug_conflict() -> CategoryAlreadyExists:
        # Deux noms différents peuvent donner le même identifiant d'URL
        # (« Tech » et « Tech ! » → « tech »). Sans ce contrôle, la base
        # refuserait l'enregistrement avec une erreur 500.
        return CategoryAlreadyExists(
            detail="Une catégorie au nom trop proche existe déjà (même identifiant d'URL).",
        )

    @classmethod
    def create(cls, *, actor, validated_data: dict, request=None) -> Category:
        with transaction.atomic():
            try:
                # Point de sauvegarde : en cas de doublon, seule cette
                # instruction est annulée et on renvoie une erreur propre.
                with transaction.atomic():
                    category = CategoryService.create_category(validated_data=validated_data)
            except IntegrityError:
                raise cls._slug_conflict()

            AuditService.log(
                actor=actor,
                action=AuditAction.CATEGORY_CREATED,
                entity_type=AuditEntity.CATEGORY,
                entity_id=category.pk,
                description=f"Création de la catégorie « {category.name} »",
                metadata={"name": category.name, "slug": category.slug},
                request=request,
            )
        return category

    @classmethod
    def update(cls, *, actor, category_id, validated_data: dict, request=None) -> Category:
        """Modifie les champs envoyés et enregistre l'avant / après dans l'audit."""
        with transaction.atomic():
            category = cls._lock(category_id)
            changes = {
                field: {"before": getattr(category, field), "after": value}
                for field, value in validated_data.items()
                if getattr(category, field) != value
            }
            if not changes:
                return category  # rien n'a changé : pas de ligne d'audit inutile

            try:
                with transaction.atomic():
                    category = CategoryService.update_category(
                        category=category,
                        validated_data={field: change["after"] for field, change in changes.items()},
                    )
            except IntegrityError:
                raise cls._slug_conflict()

            AuditService.log(
                actor=actor,
                action=AuditAction.CATEGORY_UPDATED,
                entity_type=AuditEntity.CATEGORY,
                entity_id=category.pk,
                description=f"Modification de la catégorie « {category.name} »",
                metadata={"changes": changes},
                request=request,
            )
        return category

    @classmethod
    def set_active(cls, *, actor, category_id, active: bool, reason: str, request=None) -> Category:
        """
        Désactive (active=False) ou réactive (active=True) une catégorie.
        Désactiver ne touche pas aux événements : la catégorie disparaît
        seulement des listes publiques.
        """
        with transaction.atomic():
            category = cls._lock(category_id)
            if category.is_active == active:
                raise CategoryAlreadyActive() if active else CategoryAlreadyInactive()

            category.is_active = active
            category.save(update_fields=["is_active", "updated_at"])

            AuditService.log(
                actor=actor,
                action=AuditAction.CATEGORY_ACTIVATED if active else AuditAction.CATEGORY_DEACTIVATED,
                entity_type=AuditEntity.CATEGORY,
                entity_id=category.pk,
                description=(
                    f"{'Réactivation' if active else 'Désactivation'} "
                    f"de la catégorie « {category.name} »"
                ),
                reason=reason,
                metadata={"events_count": category.events.count()},
                request=request,
            )
        return category

    @classmethod
    def delete(cls, *, actor, category_id, request=None) -> None:
        """Supprime une catégorie inutilisée (sinon CategoryInUse → 409)."""
        with transaction.atomic():
            category = cls._lock(category_id)
            snapshot = {"name": category.name, "slug": category.slug}
            category_pk = category.pk

            CategoryService.delete_category(category=category)

            # La catégorie n'existe plus : l'audit garde son nom et son id.
            AuditService.log(
                actor=actor,
                action=AuditAction.CATEGORY_DELETED,
                entity_type=AuditEntity.CATEGORY,
                entity_id=category_pk,
                description=f"Suppression de la catégorie « {snapshot['name']} »",
                metadata=snapshot,
                request=request,
            )
