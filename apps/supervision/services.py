"""
Services métier du module Supervision.

Phase S1 : AuditService, utilisé par toutes les actions administratives.
Phase S2 : UserSupervisionService (suspension / réactivation de comptes).

Règle d'usage : chaque service d'action appelle AuditService.log() DANS
SA transaction (transaction.atomic). Ainsi, soit l'action ET sa trace
sont enregistrées, soit aucune des deux : jamais d'action sans trace.
"""

import logging
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import User
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
    SecurityGuardDenied,
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

        if denial is not None:
            cls._log_denied(
                actor=actor, action=AuditAction.USER_ACTIVATED, target=target,
                reason=reason, error=denial, request=request,
            )
            raise denial
        return target
