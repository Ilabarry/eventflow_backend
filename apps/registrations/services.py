"""
Services métier du module Registration.

⚠️ POINT CRITIQUE : la création d'une inscription doit être protégée
contre les accès concurrents. Deux participants ne doivent JAMAIS
pouvoir dépasser la capacité d'un événement, ni le stock d'un type de
ticket, même s'ils s'inscrivent simultanément.

Le stock d'un type de ticket est RÉSERVÉ dès l'inscription (on compte les
inscriptions actives, pas seulement les tickets déjà émis), sinon des dizaines
de participants pourraient s'inscrire puis payer pour un stock épuisé.
"""

import logging
import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.events.constants import CapacityType, ParticipationType
from apps.events.models import Event
from apps.registrations.constants import (
    ACTIVE_STATUSES,
    REFERENCE_ALPHABET,
    REFERENCE_MAX_LENGTH,  # noqa: F401
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
            RegistrationNotAllowed: Si l'utilisateur n'est pas actif
                ou si l'événement n'accepte plus d'inscriptions.
            PaymentNotPayable: Si l'événement est PAID sans ticket_type valide.
            TicketTypeNotOnSale / TicketTypeSoldOut: type de ticket fermé ou épuisé.
        """
        from apps.registrations.validators import validate_event_is_open

        # 1. Vérifier que le participant est actif
        if not participant.is_active:
            raise RegistrationNotAllowed(
                detail="Votre compte est désactivé. Contactez le support."
            )

        # 2. Verrouiller l'événement (SELECT ... FOR UPDATE)
        locked_event = Event.objects.select_for_update().get(pk=event.pk)

        # 2b. Re-vérifier l'ouverture de l'événement sous verrou
        try:
            validate_event_is_open(locked_event)
        except DjangoValidationError as e:
            raise RegistrationNotAllowed(detail=" ".join(e.messages))

        # 3. Vérifier la capacité (uniquement si LIMITED)
        if (
            locked_event.capacity_type == CapacityType.LIMITED
            and locked_event.capacity_limit is not None
        ):
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
            # Le ticket_type doit appartenir à l'événement
            if ticket_type.event_id != locked_event.id:
                raise PaymentNotPayable(
                    detail="Le type de ticket n'appartient pas à cet événement."
                )
            # Le ticket_type doit être actif
            if not ticket_type.is_active:
                raise PaymentNotPayable(
                    detail="Ce type de ticket n'est plus disponible."
                )

            # Verrouiller le type de ticket, puis vérifier vente et stock.
            # Imports locaux : évitent un import circulaire avec le module tickets.
            from apps.tickets.models import TicketType
            from common.exceptions.business import (
                TicketTypeNotOnSale,
                TicketTypeSoldOut,
            )

            locked_tt = TicketType.objects.select_for_update().get(pk=ticket_type.pk)

            if not locked_tt.is_on_sale():
                raise TicketTypeNotOnSale()

            # Réservation du stock : on compte les inscriptions actives
            # (PENDING ou CONFIRMED) de ce type, pas seulement les tickets émis.
            if locked_tt.quantity_total is not None:
                reserved = Registration.objects.filter(
                    ticket_type=locked_tt,
                    status__in=ACTIVE_STATUSES,
                ).count()
                if reserved >= locked_tt.quantity_total:
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

        # Notifier l'organisateur
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=locked_event.organizer,
                    title="Nouvelle inscription",
                    message=(
                        f"{participant.full_name} s'est inscrit à « {locked_event.title} ». "
                        f"Référence : {registration.reference}."
                    ),
                    notification_type=NotificationType.REGISTRATION,
                    related_entity_type="registration",
                    related_entity_id=str(registration.id),
                    metadata={"url": f"/organizer/participants/{registration.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on registration creation | err=%s", e)

        return registration

    # ------------------------------------------------------------------
    # ANNULATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def cancel_registration(
        *, registration: Registration, cancelled_by_user=None
    ) -> Registration:
        """
        Annule une inscription.

        `cancelled_by_user=None` signifie « annulation système » (ex : après
        un remboursement).

        Règles :
            - Verrou sur l'inscription (pas de course annulation/confirmation).
            - Transition vérifiée via la machine d'états du modèle.
            - Une inscription dont le paiement est SUCCESS ne peut pas être
              annulée : le paiement doit d'abord être remboursé (le
              remboursement annule ensuite l'inscription automatiquement).
            - Les paiements PENDING encore ouverts sont annulés.
            - Le ticket VALID est annulé : un QR code ne doit plus donner accès.
        """
        from django.utils import timezone
        from apps.payments.constants import PaymentStatus
        from apps.payments.models import Payment
        from apps.tickets.constants import TicketStatus
        from apps.tickets.models import Ticket
        from apps.tickets.services import TicketService

        # Verrou + rechargement (on garde le même objet pour l'appelant)
        Registration.objects.select_for_update().get(pk=registration.pk)
        registration.refresh_from_db()

        if registration.status == RegistrationStatus.CANCELLED:
            raise RegistrationAlreadyCancelled()

        if not registration.can_transition_to(RegistrationStatus.CANCELLED):
            raise RegistrationNotAllowed(
                detail=f"Transition '{registration.status}' → 'CANCELLED' non autorisée."
            )

        # Une inscription payée doit d'abord être remboursée
        if Payment.objects.filter(
            registration=registration, status=PaymentStatus.SUCCESS
        ).exists():
            raise RegistrationNotAllowed(
                detail=(
                    "Cette inscription est payée : un remboursement est "
                    "nécessaire avant l'annulation."
                )
            )

        now = timezone.now()

        # Fermer les paiements encore en attente
        Payment.objects.filter(
            registration=registration, status=PaymentStatus.PENDING
        ).update(status=PaymentStatus.CANCELLED, cancelled_at=now, updated_at=now)

        # Révoquer le ticket (s'il est encore valide)
        ticket = Ticket.objects.filter(registration=registration).first()
        if ticket is not None and ticket.status == TicketStatus.VALID:
            TicketService.cancel_ticket(ticket=ticket)

        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = now
        registration.save(update_fields=["status", "cancelled_at", "updated_at"])

        logger.info(
            "Registration cancelled | ref=%s | by=%s",
            registration.reference,
            cancelled_by_user.email if cancelled_by_user else "system",
        )

        # Notifier le participant
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=registration.participant,
                    title="Inscription annulée",
                    message=(
                        f"Votre inscription à « {registration.event.title} » a été annulée. "
                        f"Référence : {registration.reference}."
                    ),
                    notification_type=NotificationType.REGISTRATION,
                    related_entity_type="registration",
                    related_entity_id=str(registration.id),
                    metadata={"url": f"/participant/inscriptions/{registration.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on registration cancel | err=%s", e)

        return registration

    # ------------------------------------------------------------------
    # CONFIRMATION (organisateur ou système, futur Payment)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def confirm_registration(*, registration: Registration, confirmed_by_user=None) -> Registration:
        """Confirme une inscription en PENDING."""
        # Verrou + rechargement (on garde le même objet pour l'appelant)
        Registration.objects.select_for_update().get(pk=registration.pk)
        registration.refresh_from_db()

        if not registration.can_transition_to(RegistrationStatus.CONFIRMED):
            raise RegistrationNotAllowed(
                detail=f"Transition '{registration.status}' → 'CONFIRMED' non autorisée."
            )

        registration.status = RegistrationStatus.CONFIRMED
        registration.save(update_fields=["status", "updated_at"])

        logger.info(
            "Registration confirmed | ref=%s | by=%s",
            registration.reference,
            confirmed_by_user.email if confirmed_by_user else "system",
        )

        # Notifier le participant
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=registration.participant,
                    title="Inscription confirmée",
                    message=(
                        f"Votre inscription à « {registration.event.title} » est confirmée. "
                        f"Référence : {registration.reference}."
                    ),
                    notification_type=NotificationType.REGISTRATION,
                    related_entity_type="registration",
                    related_entity_id=str(registration.id),
                    metadata={"url": f"/participant/inscriptions/{registration.id}"},
                )
        except Exception as e:
            logger.warning(
                "Notification failed on registration confirm | reg=%s | err=%s",
                registration.reference, e,
            )

        return registration