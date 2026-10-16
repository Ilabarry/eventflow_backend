"""
Selectors du module Event.

Un selector est une fonction qui retourne un QuerySet optimisé.
Il centralise les requêtes complexes et évite les duplications.

Avantages :
    - Optimisation centralisée (select_related, prefetch_related)
    - Testable unitairement
    - Réutilisable (vues publiques, vues organisateur, vues admin)
"""

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN
from apps.events.constants import EventStatus
from apps.events.models import Category, Event


# ==================================================================
# EVENT — Selectors publics
# ==================================================================
def get_public_events() -> QuerySet[Event]:
    """
    Retourne les événements visibles publiquement.

    Critères :
        - status = PUBLISHED
        - Tri par date de début croissante

    Optimisations :
        - select_related('organizer', 'category') → évite N+1
    """
    return (
        Event.objects
        .filter(status=EventStatus.PUBLISHED)
        .select_related("organizer", "category")
        .order_by("start_at")
    )


def get_upcoming_events() -> QuerySet[Event]:
    """Événements publiés dont la date de début est dans le futur."""
    return get_public_events().filter(start_at__gte=timezone.now())


def get_past_events() -> QuerySet[Event]:
    """Événements publiés dont la date de fin est passée."""
    return get_public_events().filter(end_at__lt=timezone.now())


def get_event_by_id(event_id) -> Event | None:
    """
    Retourne un événement par son ID (avec relations préchargées).

    Args:
        event_id: UUID de l'événement.

    Returns:
        L'instance Event ou None si introuvable.
    """
    return (
        Event.objects
        .select_related("organizer", "category")
        .filter(id=event_id)
        .first()
    )


# ==================================================================
# EVENT — Selectors organisateur
# ==================================================================
def get_organizer_events(organizer) -> QuerySet[Event]:
    """
    Retourne tous les événements d'un organisateur (tous statuts).

    Utilisé par GET /api/events/my/.
    """
    return (
        Event.objects
        .filter(organizer=organizer)
        .select_related("organizer", "category")
        .order_by("-created_at")
    )


# ==================================================================
# EVENT — Selectors admin
# ==================================================================
def get_all_events() -> QuerySet[Event]:
    """
    Retourne tous les événements (pour les administrateurs).

    Utilisé par les vues admin (supervision).
    """
    return (
        Event.objects
        .all()
        .select_related("organizer", "category")
        .order_by("-created_at")
    )


# ==================================================================
# EVENT — Selectors contextuels
# ==================================================================
def get_events_for_user(user) -> QuerySet[Event]:
    """
    Retourne les événements visibles par un utilisateur donné.

    Règles :
        - Anonyme : PUBLISHED uniquement
        - Participant : PUBLISHED uniquement
        - Organisateur : PUBLISHED (tous) + ses propres événements (tous statuts)
        - Admin : tous

    Args:
        user: L'utilisateur connecté (ou AnonymousUser).

    Returns:
        QuerySet filtré selon le rôle.
    """
    # Anonyme
    if not user or not user.is_authenticated:
        return get_public_events()

    # Admin
    if user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN):
        return get_all_events()

    # Organisateur : ses événements + les publiés des autres
    from django.db.models import Q

    return (
        Event.objects
        .filter(Q(status=EventStatus.PUBLISHED) | Q(organizer=user))
        .select_related("organizer", "category")
        .order_by("-created_at")
    )


# ==================================================================
# CATEGORY — Selectors
# ==================================================================
def get_categories() -> QuerySet[Category]:
    """Retourne toutes les catégories."""
    return Category.objects.all().order_by("name")


def get_active_categories() -> QuerySet[Category]:
    """Retourne uniquement les catégories actives (pour l'API publique)."""
    return Category.objects.filter(is_active=True).order_by("name")


def get_category_by_id(category_id) -> Category | None:
    """Retourne une catégorie par son ID."""
    return Category.objects.filter(id=category_id).first()