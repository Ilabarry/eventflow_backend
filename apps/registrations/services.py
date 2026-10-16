"""
Services métier du module Registration.

⚠️ POINT CRITIQUE : la création d'une inscription doit être protégée
contre les accès concurrents. Deux participants ne doivent JAMAIS
pouvoir dépasser la capacité d'un événement, même s'ils s'inscrivent
simultanément.

Stratégie :
    1. Ouvrir une transaction.
    2. Verrouiller la ligne de l'événement avec select_for_update().
    3. Compter les inscriptions actives.
    4. Vérifier la capacité.
    5. Créer l'inscription.
    6. Commit.

Ce verrou est sur UNE ligne (l'événement), pas sur toute la table.
Les inscriptions à d'autres événements ne sont pas bloquées.
"""

import logging
import secrets
import string

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
        """
        Génère une référence unique de type EVF-REG-2026-A8K3X2.

        Utilise `secrets` (cryptographiquement sûr) et exclut les
        caractères ambigus (0/O, 1/I/L) pour éviter les confusions.
        """
        from django.utils import timezone

        year = timezone.now().year
        suffix = "".join(
            secrets.choice(REFERENCE_ALPHABET)
            for _ in range(REFERENCE_SUFFIX_LENGTH)
        )
        return f"{REFERENCE_PREFIX}-{year}-{suffix}"

    @staticmethod
    def _generate_unique_reference() -> str:
        """
        Génère une référence unique avec retry en cas de collision.

        La probabilité de collision est très faible (32^6 ≈ 1 milliard),
        mais on protège quand même.
        """
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
    def create_registration(*, participant, event: Event) -> Registration:
        """
        Crée une inscription pour un participant à un événement.

        ⚠️ CRITIQUE : on verrouille la ligne de l'événement pour éviter
        le dépassement de capacité en cas d'inscriptions simultanées.

        Args:
            participant: L'utilisateur qui s'inscrit (request.user).
            event: L'instance Event (récupérée par le serializer).

        Returns:
            L'instance Registration créée.

        Raises:
            AlreadyRegistered: Si le participant a déjà une inscription active.
            EventFull: Si la capacité est atteinte.
            RegistrationNotAllowed: Si l'utilisateur n'est pas actif.
        """
        # 1. Vérifier que le participant est actif
        if not participant.is_active:
            raise RegistrationNotAllowed(
                detail="Votre compte est désactivé. Contactez le support."
            )

        # 2. Verrouiller l'événement (SELECT ... FOR UPDATE)
        #    Cela empêche deux transactions concurrentes de lire
        #    le même compteur d'inscriptions avant insertion.
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

        # 5. Déterminer le statut initial
        #    - FREE → CONFIRMED immédiatement
        #    - PAID → PENDING (en attente de paiement, futur module)
        initial_status = (
            RegistrationStatus.CONFIRMED
            if locked_event.participation_type == ParticipationType.FREE
            else RegistrationStatus.PENDING
        )

        # 6. Créer l'inscription
        try:
            registration = Registration.objects.create(
                participant=participant,
                event=locked_event,
                reference=RegistrationService._generate_unique_reference(),
                status=initial_status,
            )
        except IntegrityError as e:
            # La UniqueConstraint a bloqué (double inscription en concurrence)
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
        """
        Annule une inscription.

        L'inscription n'est PAS supprimée : son statut passe à CANCELLED
        et cancelled_at est renseigné (soft delete).

        Raises:
            RegistrationAlreadyCancelled: Si déjà annulée.
        """
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

        Utilisé par :
            - L'organisateur (confirmation manuelle)
            - Le module Payment (confirmation automatique après paiement)

        Raises:
            RegistrationNotAllowed: Si la transition n'est pas autorisée.
        """
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

        return registration