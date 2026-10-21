"""
Services métier du module Registration.

⚠️ POINT CRITIQUE : la création d'une inscription doit être protégée
contre les accès concurrents. Deux participants ne doivent JAMAIS
pouvoir dépasser la capacité d'un événement, même s'ils s'inscrivent
simultanément.
"""

import logging
import secrets

from django.db import IntegrityError, transaction

from apps.events.constants import CapacityType, ParticipationType
from apps.events.models import Event
from apps.registrations.constants import (
    ACTIVE_STATUSES,
    REFERENCE_ALPHABET,
    REFERENCE_MAX_LENGTH,
    REFERENCE_PREFIX,
    REFERENCE_SUFFIX_LENGTH,
    RegistrationStatus,
)
from apps.registrations.models import Registration
from common.exceptions.business import (
    AlreadyRegistered,
    EventFull,
    PaymentNotPayable,
    RegistrationAlreadyCancelled,
    RegistrationNotAllowed,
)

logger = logging.getLogger(__name__)


class RegistrationService:
    """Service métier pour les inscriptions."""

    # ------------------------------------------------------------------
    # GÉNÉRATION DE RÉFÉRENCE
    # ------------------------------------------------------------------
    @staticmethod
    def generate_reference() -> str:
        """Génère une référence unique EVF-REG-YYYY-XXXXXX."""
        from django.utils import timezone
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
            reference = RegistrationService.generate_reference()
            if not Registration.objects.filter(reference=reference).exists():
                return reference
        raise RuntimeError("Impossible de générer une référence unique.")

    # ------------------------------------------------------------------
    # CRÉATION D'UNE INSCRIPTION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create_registration(
        *, participant, event: Event, ticket_type=None
    ) -> Registration:
        """
        Crée une inscription pour un participant à un événement.

        Args:
            participant: L'utilisateur qui s'inscrit (request.user).
            event: L'instance Event.
            ticket_type: TicketType (obligatoire pour PAID, None pour FREE).

        Returns:
            L'instance Registration créée.

        Raises:
            AlreadyRegistered: Si le participant a déjà une inscription active.
            EventFull: Si la capacité est atteinte.
            RegistrationNotAllowed: Si l'utilisateur n'est pas actif.
            PaymentNotPayable: Si l'événement est PAID sans ticket_type.
        """
        # 1. Vérifier que le participant est actif
        if not participant.is_active:
            raise RegistrationNotAllowed(
                detail="Votre compte est désactivé. Contactez le support."
            )

        # 2. Verrouiller l'événement (SELECT ... FOR UPDATE)
        locked_event = Event.objects.select_for_update().get(pk=event.pk)

        # 3. Vérifier la capacité (uniquement si LIMITED)
        if locked_event.capacity_type == CapacityType.LIMITED:
            active_count = Registration.objects.filter(
                event=locked_event,
                status__in=ACTIVE_STATUSES,
            ).count()

            if active_count >= locked_event.capacity_limit:
                logger.warning(
                    "Registration rejected (capacity full) | event=%s | user=%s",
                    locked_event.id, participant.email,
                )
                raise EventFull(
                    detail=f"Cet événement est complet ({active_count}/{locked_event.capacity_limit})."
                )

        # 4. Vérifier qu'il n'y a pas de double inscription active
        if Registration.objects.filter(
            participant=participant,
            event=locked_event,
            status__in=ACTIVE_STATUSES,
        ).exists():
            logger.info(
                "Registration rejected (already registered) | event=%s | user=%s",
                locked_event.id, participant.email,
            )
            raise AlreadyRegistered()

        # 5. Vérifier le ticket_type pour les événements payants
        if locked_event.participation_type == ParticipationType.PAID:
            if ticket_type is None:
                raise PaymentNotPayable(
                    detail="Un type de ticket est obligatoire pour cet événement payant."
                )
            # Vérifier que le ticket_type appartient bien à l'événement
            if ticket_type.event_id != locked_event.id:
                raise PaymentNotPayable(
                    detail="Le type de ticket n'appartient pas à cet événement."
                )
            # Vérifier que le ticket_type est actif
            if not ticket_type.is_active:
                raise PaymentNotPayable(
                    detail="Ce type de ticket n'est plus disponible."
                )
            # Vérifier la disponibilité
            if ticket_type.is_sold_out:
                from common.exceptions.business import TicketTypeSoldOut
                raise TicketTypeSoldOut()

        # 6. Déterminer le statut initial
        initial_status = (
            RegistrationStatus.CONFIRMED
            if locked_event.participation_type == ParticipationType.FREE
            else RegistrationStatus.PENDING
        )

        # 7. Créer l'inscription
        try:
            registration = Registration.objects.create(
                participant=participant,
                event=locked_event,
                ticket_type=ticket_type,
                reference=RegistrationService._generate_unique_reference(),
                status=initial_status,
            )
        except IntegrityError as e:
            logger.warning(
                "Registration IntegrityError | event=%s | user=%s | err=%s",
                locked_event.id, participant.email, str(e),
            )
            raise AlreadyRegistered()

        logger.info(
            "Registration created | ref=%s | event=%s | user=%s | status=%s",
            registration.reference, locked_event.id, participant.email, initial_status,
        )

        return registration

    # ------------------------------------------------------------------
    # ANNULATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def cancel_registration(*, registration: Registration, cancelled_by_user) -> Registration:
        """Annule une inscription."""
        if registration.status == RegistrationStatus.CANCELLED:
            raise RegistrationAlreadyCancelled()

        registration.status = RegistrationStatus.CANCELLED
        from django.utils import timezone
        registration.cancelled_at = timezone.now()
        registration.save(update_fields=["status", "cancelled_at", "updated_at"])

        logger.info(
            "Registration cancelled | ref=%s | by=%s",
            registration.reference, cancelled_by_user.email,
        )

        return registration

    # ------------------------------------------------------------------
    # CONFIRMATION (organisateur ou système, futur Payment)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def confirm_registration(*, registration: Registration, confirmed_by_user=None) -> Registration:
        """
        Confirme une inscription en PENDING.

        ⚠️ GARANTIE D'INTÉGRITÉ :
        Si un `ticket_type` est défini (événement payant avec ticket),
        le ticket est généré DANS LA MÊME TRANSACTION que la confirmation.
        Si la génération du ticket échoue, la confirmation est ROLLBACKÉE
        (la Registration reste PENDING).

        Cela garantit qu'il n'existe jamais de Registration CONFIRMED
        sans Ticket correspondant.

        Raises:
            RegistrationNotAllowed: Si la transition n'est pas autorisée.
            Exception: Toute erreur de génération de ticket remonte
                et déclenche le rollback.
        """
        if not registration.can_transition_to(RegistrationStatus.CONFIRMED):
            raise RegistrationNotAllowed(
                detail=f"Transition '{registration.status}' → 'CONFIRMED' non autorisée."
            )

        # 1. Mettre à jour le statut de la Registration
        registration.status = RegistrationStatus.CONFIRMED
        registration.save(update_fields=["status", "updated_at"])

        # 2. Si un ticket_type est défini, générer le ticket
        #    DANS LA MÊME TRANSACTION (rollback automatique si échec)
        if registration.ticket_type is not None:
            from apps.tickets.services import TicketService
            ticket = TicketService.issue_ticket_for_registration(registration)
            logger.info(
                "Ticket issued on registration confirm | ticket=%s | reg=%s",
                ticket.reference, registration.reference,
            )

        logger.info(
            "Registration confirmed | ref=%s | by=%s",
            registration.reference,
            confirmed_by_user.email if confirmed_by_user else "system",
        )

        return registration