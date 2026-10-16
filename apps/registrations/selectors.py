"""
Selectors du module Registration.

Centralise les requêtes de lecture et optimise avec select_related.
Évite le N+1 query problem.
"""

from django.db.models import QuerySet

from apps.accounts.constants import ROLE_ADMIN
from apps.events.models import Event
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration


# ==================================================================
# LECTURE PAR ID
# ==================================================================
def get_registration_by_id(registration_id) -> Registration | None:
    """
    Retourne une inscription par son UUID, avec relations préchargées.

    Optimisation : select_related('participant', 'event', 'event__organizer', 'event__category')
    pour éviter N+1 quand on sérialise.
    """
    return (
        Registration.objects
        .select_related(
            "participant",
            "event",
            "event__organizer",
            "event__category",
        )
        .filter(id=registration_id)
        .first()
    )


# ==================================================================
# LECTURES PAR CONTEXTE
# ==================================================================
def get_user_registrations(user) -> QuerySet[Registration]:
    """
    Retourne toutes les inscriptions d'un utilisateur.

    Utilisé par GET /api/registrations/ (participant).
    """
    return (
        Registration.objects
        .filter(participant=user)
        .select_related("event", "event__organizer", "event__category")
        .order_by("-registered_at")
    )


def get_event_registrations(event: Event, status: str = None) -> QuerySet[Registration]:
    """
    Retourne toutes les inscriptions d'un événement (organisateur).

    Args:
        event: L'événement.
        status: Filtre optionnel sur le statut.

    Utilisé par GET /api/events/{id}/registrations/.
    """
    qs = (
        Registration.objects
        .filter(event=event)
        .select_related("participant", "event")
        .order_by("-registered_at")
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def get_confirmed_registrations(event: Event) -> QuerySet[Registration]:
    """Retourne les inscriptions confirmées d'un événement."""
    return get_event_registrations(event, status=RegistrationStatus.CONFIRMED)


def get_pending_registrations(event: Event) -> QuerySet[Registration]:
    """Retourne les inscriptions en attente d'un événement."""
    return get_event_registrations(event, status=RegistrationStatus.PENDING)


# ==================================================================
# LECTURES POUR ADMIN
# ==================================================================
def get_all_registrations() -> QuerySet[Registration]:
    """
    Retourne toutes les inscriptions (admin).

    Utilisé par GET /api/registrations/ quand l'utilisateur est admin.
    """
    return (
        Registration.objects
        .select_related("participant", "event", "event__organizer")
        .order_by("-registered_at")
    )


# ==================================================================
# SELECTOR CONTEXTUEL
# ==================================================================
def get_registrations_for_user(user) -> QuerySet[Registration]:
    """
    Retourne les inscriptions visibles par un utilisateur.

    Règles :
        - Participant : ses propres inscriptions
        - Organisateur : ses inscriptions + celles de ses événements
        - Admin : toutes

    Utilisé par GET /api/registrations/.
    """
    from django.db.models import Q

    if not user or not user.is_authenticated:
        return Registration.objects.none()

    # Admin
    if user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN):
        return get_all_registrations()

    # Organisateur : ses inscriptions + inscriptions de ses événements
    from apps.accounts.constants import ROLE_ORGANIZER
    if user.has_role(ROLE_ORGANIZER):
        return (
            Registration.objects
            .filter(Q(participant=user) | Q(event__organizer=user))
            .select_related("participant", "event", "event__organizer")
            .distinct()
            .order_by("-registered_at")
        )

    # Participant simple
    return get_user_registrations(user)


# ==================================================================
# COMPTAGE (utilisé par Event.calculate_availability)
# ==================================================================
def count_active_registrations(event: Event) -> int:
    """
    Compte les inscriptions actives d'un événement.

    Utilisé par Event.calculate_availability() pour calculer
    la disponibilité réelle.
    """
    return Registration.objects.filter(
        event=event,
        status__in=[RegistrationStatus.PENDING, RegistrationStatus.CONFIRMED],
    ).count()