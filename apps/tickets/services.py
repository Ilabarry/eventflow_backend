"""
Services métier du module Tickets.

⚠️ POINTS CRITIQUES :
    1. L'émission d'un ticket est IDEMPOTENTE (pas de doublon) et sérialisée
       par un verrou sur l'inscription.
    2. quantity_sold est modifié de façon atomique (F expressions).
    3. Un ticket n'est émis que si la Registration est CONFIRMED.
    4. Le stock d'un TicketType est RÉSERVÉ à l'inscription (voir
       RegistrationService.create_registration) : l'émission ne revérifie donc
       ni la fenêtre de vente ni le stock, pour ne jamais refuser un ticket
       à quelqu'un qui a déjà payé.
    5. mark_as_used verrouille le ticket : un même QR ne peut pas être
       accepté deux fois, même scanné simultanément par deux appareils.
"""

import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.tickets.constants import (
    REFERENCE_ALPHABET,
    REFERENCE_PREFIX,
    REFERENCE_SUFFIX_LENGTH,
    TicketStatus,
)
from apps.tickets.models import Ticket, TicketType
from common.exceptions.business import (
    TicketNotUsable,
    TicketTypeFromOtherEvent,
    TicketTypeNotOnSale,
)

logger = logging.getLogger(__name__)

# Longueur maximale acceptée pour un payload QR (référence + "|" + 64 hex)
QR_PAYLOAD_MAX_LENGTH = 200


# ==================================================================
# SERVICE : TicketType
# ==================================================================
class TicketTypeService:
    """Service métier pour les types de tickets."""

    @staticmethod
    @transaction.atomic
    def create_ticket_type(*, event, validated_data: dict) -> TicketType:
        """Crée un TicketType."""
        ticket_type = TicketType.objects.create(event=event, **validated_data)
        logger.info(
            "TicketType created | id=%s | event=%s | name=%s",
            ticket_type.id, event.id, ticket_type.name,
        )
        return ticket_type

    @staticmethod
    @transaction.atomic
    def update_ticket_type(*, ticket_type: TicketType, validated_data: dict) -> TicketType:
        """Met à jour un TicketType."""
        for field, value in validated_data.items():
            setattr(ticket_type, field, value)
        ticket_type.save()
        logger.info("TicketType updated | id=%s", ticket_type.id)
        return ticket_type

    @staticmethod
    @transaction.atomic
    def deactivate_ticket_type(*, ticket_type: TicketType) -> TicketType:
        """
        Désactive un TicketType (au lieu de le supprimer).

        On ne supprime JAMAIS un TicketType qui a des tickets émis.
        """
        ticket_type.is_active = False
        ticket_type.save(update_fields=["is_active", "updated_at"])
        logger.info("TicketType deactivated | id=%s", ticket_type.id)
        return ticket_type

    @staticmethod
    @transaction.atomic
    def delete_ticket_type(*, ticket_type: TicketType) -> None:
        """
        Supprime un TicketType.

        Autorisé UNIQUEMENT si ni ticket ni inscription ne s'y réfèrent :
        supprimer un type utilisé par des inscriptions en attente ferait
        retomber leur prix sur le prix de base de l'événement.
        """
        if (
            ticket_type.tickets.exists()
            or Registration.objects.filter(ticket_type=ticket_type).exists()
        ):
            raise TicketTypeNotOnSale(
                detail=(
                    "Impossible de supprimer un type de ticket déjà utilisé par "
                    "des inscriptions. Désactivez-le à la place."
                )
            )
        ticket_type_id = ticket_type.id
        ticket_type.delete()
        logger.info("TicketType deleted | id=%s", ticket_type_id)

    @staticmethod
    def check_availability(ticket_type: TicketType, at=None) -> dict:
        """
        Vérifie la disponibilité d'un TicketType.

        Returns:
            dict avec available, is_on_sale, is_sold_out, etc.
        """
        at = at or timezone.now()
        return {
            "is_active": ticket_type.is_active,
            "is_on_sale": ticket_type.is_on_sale(at),
            "is_sold_out": ticket_type.is_sold_out,
            "available_quantity": ticket_type.available_quantity,
            "quantity_total": ticket_type.quantity_total,
            "quantity_sold": ticket_type.quantity_sold,
        }


# ==================================================================
# SERVICE : Ticket
# ==================================================================
class TicketService:
    """Service métier pour les tickets individuels."""

    # ------------------------------------------------------------------
    # GÉNÉRATION DE RÉFÉRENCE
    # ------------------------------------------------------------------
    @staticmethod
    def generate_reference() -> str:
        """Génère une référence unique EVF-TKT-YYYY-XXXXXXXX."""
        year = timezone.now().year
        suffix = "".join(
            secrets.choice(REFERENCE_ALPHABET)
            for _ in range(REFERENCE_SUFFIX_LENGTH)
        )
        return f"{REFERENCE_PREFIX}-{year}-{suffix}"

    @staticmethod
    def _generate_unique_reference() -> str:
        """Génère une référence unique avec retry."""
        for _ in range(10):
            ref = TicketService.generate_reference()
            if not Ticket.objects.filter(reference=ref).exists():
                return ref
        raise RuntimeError("Impossible de générer une référence unique.")

    # ------------------------------------------------------------------
    # ÉMISSION D'UN TICKET (CRITIQUE)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def issue_ticket_for_registration(registration: Registration) -> Ticket:
        """
        Émet un ticket pour une inscription CONFIRMED.

        ⚠️ IDEMPOTENT : si un ticket existe déjà, retourne l'existant.

        Étapes :
            0. Verrouiller l'inscription (sérialise les émissions concurrentes)
               et relire son statut en base.
            1. Registration CONFIRMED.
            2. Pas de ticket existant.
            3. TicketType appartenant au bon Event (si défini).
            4. Créer le ticket, puis incrémenter quantity_sold.

        La fenêtre de vente et le stock ont été vérifiés (et réservés) à
        l'inscription : on ne les revérifie pas ici, pour ne jamais refuser
        un ticket à quelqu'un qui a déjà payé.

        Raises:
            TicketNotUsable: inscription non CONFIRMED.
            TicketTypeFromOtherEvent: type de ticket d'un autre événement.
        """
        # 0. Verrou + relecture du statut réel
        locked_registration = Registration.objects.select_for_update().get(
            pk=registration.pk
        )

        # 1. Registration CONFIRMED
        if locked_registration.status != RegistrationStatus.CONFIRMED:
            raise TicketNotUsable(
                detail=(
                    "Un ticket ne peut être émis que pour une inscription CONFIRMED. "
                    f"Statut actuel : {locked_registration.status}."
                )
            )

        # 2. Idempotence
        existing = Ticket.objects.filter(registration=locked_registration).first()
        if existing:
            logger.info(
                "Ticket already exists (idempotent) | ticket=%s | reg=%s",
                existing.reference, locked_registration.reference,
            )
            return existing

        # 3. Cohérence TicketType / Event
        ticket_type = locked_registration.ticket_type
        if ticket_type and ticket_type.event_id != locked_registration.event_id:
            raise TicketTypeFromOtherEvent()

        # 4a. Créer le Ticket (dans un savepoint : une IntegrityError ne doit pas
        #     invalider la transaction parente)
        try:
            with transaction.atomic():
                ticket = Ticket.objects.create(
                    registration=locked_registration,
                    ticket_type=ticket_type,
                    reference=TicketService._generate_unique_reference(),
                    status=TicketStatus.VALID,
                )
        except IntegrityError:
            existing = Ticket.objects.filter(registration=locked_registration).first()
            if existing:
                return existing
            raise

        # 4b. Incrémenter quantity_sold de façon atomique (après la création réussie)
        if ticket_type:
            TicketType.objects.filter(pk=ticket_type.pk).update(
                quantity_sold=F("quantity_sold") + 1
            )

        logger.info(
            "Ticket issued | ref=%s | reg=%s | tt=%s",
            ticket.reference, locked_registration.reference,
            ticket_type.name if ticket_type else "none",
        )

        # Notifier le participant
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=locked_registration.participant,
                    title="Votre ticket est prêt",
                    message=(
                        f"Votre ticket pour « {locked_registration.event.title} » est disponible. "
                        f"Référence : {ticket.reference}."
                    ),
                    notification_type=NotificationType.TICKET,
                    related_entity_type="ticket",
                    related_entity_id=str(ticket.id),
                    metadata={"url": f"/participant/tickets/{ticket.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on ticket issue | err=%s", e)

        return ticket

    # ------------------------------------------------------------------
    # VALIDATION (check-in) — un ticket ne peut servir qu'UNE fois
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def mark_as_used(*, ticket: Ticket) -> Ticket:
        """
        Marque un ticket comme USED (check-in).

        Le ticket est verrouillé et relu en base : si deux scans simultanés
        du même QR arrivent, le second voit USED et est refusé.
        L'inscription associée doit aussi être CONFIRMED.
        """
        ticket = (
            Ticket.objects.select_for_update(of=("self",))
            .select_related("registration")
            .get(pk=ticket.pk)
        )

        if not ticket.can_transition_to(TicketStatus.USED):
            raise TicketNotUsable(
                detail=f"Transition '{ticket.status}' → 'USED' non autorisée."
            )

        if ticket.registration.status != RegistrationStatus.CONFIRMED:
            raise TicketNotUsable(
                detail="L'inscription associée à ce ticket n'est plus confirmée."
            )

        ticket.status = TicketStatus.USED
        ticket.used_at = timezone.now()
        ticket.save(update_fields=["status", "used_at", "updated_at"])
        logger.info("Ticket used | ref=%s", ticket.reference)
        return ticket

    # ------------------------------------------------------------------
    # ANNULATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def cancel_ticket(*, ticket: Ticket) -> Ticket:
        """Annule un ticket VALID (idempotent) et libère son stock."""
        ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=ticket.pk)

        if ticket.status == TicketStatus.CANCELLED:
            return ticket  # idempotent
        if not ticket.can_be_cancelled():
            raise TicketNotUsable(
                detail=f"Seul un ticket VALID peut être annulé. Statut : {ticket.status}."
            )

        ticket.status = TicketStatus.CANCELLED
        ticket.cancelled_at = timezone.now()
        ticket.save(update_fields=["status", "cancelled_at", "updated_at"])

        # Décrémenter quantity_sold sans jamais passer sous 0
        # (quantity_sold est un PositiveIntegerField)
        if ticket.ticket_type_id:
            TicketType.objects.filter(pk=ticket.ticket_type_id).update(
                quantity_sold=Greatest(F("quantity_sold") - 1, Value(0))
            )

        logger.info("Ticket cancelled | ref=%s", ticket.reference)
        return ticket

    # ------------------------------------------------------------------
    # EXPIRATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def expire_ticket(*, ticket: Ticket) -> Ticket:
        """Marque un ticket comme EXPIRED."""
        ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=ticket.pk)

        if not ticket.can_transition_to(TicketStatus.EXPIRED):
            raise TicketNotUsable(
                detail=f"Transition '{ticket.status}' → 'EXPIRED' non autorisée."
            )
        ticket.status = TicketStatus.EXPIRED
        ticket.save(update_fields=["status", "updated_at"])
        logger.info("Ticket expired | ref=%s", ticket.reference)
        return ticket

    # ------------------------------------------------------------------
    # QR CODE
    # ------------------------------------------------------------------
    @staticmethod
    def _qr_key() -> bytes:
        """
        Clé de signature des QR codes.

        Utilise settings.QR_SIGNING_KEY si elle est définie (recommandé :
        une clé DISTINCTE de SECRET_KEY, pour que la rotation de SECRET_KEY
        n'invalide pas les billets et qu'une fuite de la clé des JWT ne
        permette pas de forger des QR). Sinon, retombe sur SECRET_KEY.
        """
        key = getattr(settings, "QR_SIGNING_KEY", None) or settings.SECRET_KEY
        return key.encode("utf-8")

    @staticmethod
    def _qr_signature(ticket: Ticket) -> str:
        data = f"{ticket.id}|{ticket.reference}"
        return hmac.new(
            TicketService._qr_key(),
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def generate_qr_payload(ticket: Ticket) -> str:
        """
        Génère le payload QR : 'reference|signature'.

        La signature est HMAC-SHA256(ticket_id|reference). Elle ne dépend PAS
        du statut : un QR reste "authentique" après annulation. C'est le STATUT
        du ticket (et de l'inscription) qui décide de l'admission : toujours
        passer par TicketService.mark_as_used().
        """
        return f"{ticket.reference}|{TicketService._qr_signature(ticket)}"

    @staticmethod
    def verify_qr_payload(payload: str) -> Ticket | None:
        """
        Vérifie l'authenticité d'un payload QR et retourne le Ticket, ou None.

        ⚠️ Ne vérifie QUE la signature. Le ticket retourné peut être annulé,
        utilisé ou expiré : l'appelant doit contrôler son statut (mark_as_used
        le fait).
        """
        if not isinstance(payload, str) or len(payload) > QR_PAYLOAD_MAX_LENGTH:
            return None

        try:
            reference, signature = payload.strip().split("|", 1)
        except ValueError:
            return None

        # hmac.compare_digest sur des str exige de l'ASCII : sans ce contrôle,
        # un payload non ASCII provoquerait un TypeError (erreur 500).
        if not signature.isascii():
            return None

        ticket = Ticket.objects.filter(reference=reference).first()
        if not ticket:
            return None

        expected = TicketService._qr_signature(ticket)
        if not hmac.compare_digest(signature.encode("ascii"), expected.encode("ascii")):
            return None

        return ticket