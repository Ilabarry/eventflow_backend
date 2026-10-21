"""
Services métier du module Tickets.

⚠️ POINTS CRITIQUES :
    1. L'émission d'un ticket est IDEMPOTENTE (pas de doublon).
    2. La quantité (quantity_sold) est incrémentée de façon atomique.
    3. Un ticket n'est émis que si la Registration est CONFIRMED.
"""

import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
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
    TicketAlreadyExists,
    TicketNotUsable,
    TicketTypeFromOtherEvent,
    TicketTypeNotFound,
    TicketTypeNotOnSale,
    TicketTypeSoldOut,
)

logger = logging.getLogger(__name__)


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

        Autorise la suppression UNIQUEMENT si aucun ticket n'a été émis.
        """
        if ticket_type.tickets.exists():
            raise TicketTypeNotOnSale(
                detail="Impossible de supprimer un type de ticket déjà vendu. Désactivez-le à la place."
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

        Vérifications :
            1. Registration CONFIRMED.
            2. Pas de ticket existant (OneToOne).
            3. TicketType appartenant au bon Event (si défini).
            4. TicketType en vente (si défini).
            5. Quantité disponible (si limitée).

        Returns:
            Le Ticket (créé ou existant).

        Raises:
            TicketTypeFromOtherEvent: Si le TicketType n'appartient pas à l'Event.
            TicketTypeNotOnSale: Si le TicketType n'est pas en vente.
            TicketTypeSoldOut: Si le TicketType est épuisé.
        """
        # 1. Vérifier que la Registration est CONFIRMED
        if registration.status != RegistrationStatus.CONFIRMED:
            raise TicketNotUsable(
                detail=f"Un ticket ne peut être émis que pour une inscription CONFIRMED. "
                       f"Statut actuel : {registration.status}."
            )

        # 2. Vérifier si un ticket existe déjà (idempotent)
        existing = Ticket.objects.filter(registration=registration).first()
        if existing:
            logger.info(
                "Ticket already exists (idempotent) | ticket=%s | reg=%s",
                existing.reference, registration.reference,
            )
            return existing

        # 3. Si un TicketType est défini, vérifier qu'il appartient au bon Event
        ticket_type = registration.ticket_type
        if ticket_type:
            if ticket_type.event_id != registration.event_id:
                raise TicketTypeFromOtherEvent()

            # Verrouiller le TicketType pour incrémenter quantity_sold atomiquement
            locked_tt = TicketType.objects.select_for_update().get(pk=ticket_type.pk)

            # Vérifier la période de vente
            if not locked_tt.is_on_sale():
                raise TicketTypeNotOnSale()

            # Vérifier la quantité disponible
            if locked_tt.is_sold_out:
                raise TicketTypeSoldOut()

            # Incrémenter quantity_sold de façon atomique
            TicketType.objects.filter(pk=locked_tt.pk).update(
                quantity_sold=F("quantity_sold") + 1
            )

            logger.info(
                "TicketType quantity_sold incremented | tt=%s | new_sold=%s",
                locked_tt.id, locked_tt.quantity_sold + 1,
            )

        # 4. Créer le Ticket
        try:
            ticket = Ticket.objects.create(
                registration=registration,
                ticket_type=ticket_type,
                reference=TicketService._generate_unique_reference(),
                status=TicketStatus.VALID,
            )
        except IntegrityError as e:
            # OneToOne a bloqué (double émission en concurrence)
            logger.warning(
                "Ticket IntegrityError (race condition) | reg=%s | err=%s",
                registration.reference, str(e),
            )
            existing = Ticket.objects.filter(registration=registration).first()
            if existing:
                return existing
            raise

        logger.info(
            "Ticket issued | ref=%s | reg=%s | tt=%s",
            ticket.reference, registration.reference,
            ticket_type.name if ticket_type else "none",
        )
        return ticket

    # ------------------------------------------------------------------
    # VALIDATION (sera déléguée à Attendance plus tard)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def mark_as_used(*, ticket: Ticket) -> Ticket:
        """Marque un ticket comme USED (check-in)."""
        if not ticket.can_transition_to(TicketStatus.USED):
            raise TicketNotUsable(
                detail=f"Transition '{ticket.status}' → 'USED' non autorisée."
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
        """Annule un ticket VALID."""
        if ticket.status == TicketStatus.CANCELLED:
            return ticket  # idempotent
        if not ticket.can_be_cancelled():
            raise TicketNotUsable(
                detail=f"Seul un ticket VALID peut être annulé. Statut : {ticket.status}."
            )

        ticket.status = TicketStatus.CANCELLED
        ticket.cancelled_at = timezone.now()
        ticket.save(update_fields=["status", "cancelled_at", "updated_at"])

        # Décrémenter quantity_sold si TicketType
        if ticket.ticket_type_id:
            TicketType.objects.filter(pk=ticket.ticket_type_id).update(
                quantity_sold=F("quantity_sold") - 1
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
    def generate_qr_payload(ticket: Ticket) -> str:
        """
        Génère le payload QR : 'reference|signature'.

        La signature est HMAC-SHA256(ticket_id + reference, SECRET_KEY).
        """
        data = f"{ticket.id}|{ticket.reference}"
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{ticket.reference}|{signature}"

    @staticmethod
    def verify_qr_payload(payload: str) -> Ticket | None:
        """
        Vérifie un payload QR et retourne le Ticket, ou None si invalide.
        """
        try:
            reference, signature = payload.split("|", 1)
        except ValueError:
            return None

        ticket = Ticket.objects.filter(reference=reference).first()
        if not ticket:
            return None

        expected = hmac.new(
            settings.SECRET_KEY.encode(),
            f"{ticket.id}|{ticket.reference}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return None

        return ticket