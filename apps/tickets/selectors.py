from django.db import models

"""
Selectors du module Tickets.
"""

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN
from apps.tickets.constants import TicketStatus
from apps.tickets.models import Ticket, TicketType


# ==================================================================
# TICKETTYPE
# ==================================================================
def get_ticket_type_by_id(ticket_type_id) -> TicketType | None:
    return (
        TicketType.objects
        .select_related("event", "event__organizer")
        .filter(id=ticket_type_id)
        .first()
    )


def get_event_ticket_types(event, only_active: bool = False) -> QuerySet[TicketType]:
    """Tous les TicketTypes d'un événement."""
    qs = TicketType.objects.filter(event=event).select_related("event")
    if only_active:
        qs = qs.filter(is_active=True)
    return qs.order_by("price")


def get_available_ticket_types(event) -> QuerySet[TicketType]:
    """
    TicketTypes actuellement en vente pour un événement.

    Filtre :
        - is_active=True
        - sales_start_at <= now <= sales_end_at (si définis)
        - quantity_sold < quantity_total (si limité)
    """
    now = timezone.now()
    return (
        TicketType.objects
        .filter(event=event, is_active=True)
        .filter(Q(sales_start_at__isnull=True) | Q(sales_start_at__lte=now))
        .filter(Q(sales_end_at__isnull=True) | Q(sales_end_at__gte=now))
        .filter(Q(quantity_total__isnull=True) | Q(quantity_sold__lt=models.F("quantity_total")))
        .order_by("price")
    )


# ==================================================================
# TICKET
# ==================================================================
def get_ticket_by_id(ticket_id) -> Ticket | None:
    return (
        Ticket.objects
        .select_related(
            "registration",
            "registration__participant",
            "registration__event",
            "registration__event__organizer",
            "ticket_type",
        )
        .filter(id=ticket_id)
        .first()
    )


def get_user_tickets(user) -> QuerySet[Ticket]:
    return (
        Ticket.objects
        .filter(registration__participant=user)
        .select_related("registration", "registration__event", "ticket_type")
        .order_by("-issued_at")
    )


def get_event_tickets(event) -> QuerySet[Ticket]:
    return (
        Ticket.objects
        .filter(registration__event=event)
        .select_related("registration", "registration__participant", "ticket_type")
        .order_by("-issued_at")
    )


def get_valid_tickets(event) -> QuerySet[Ticket]:
    return get_event_tickets(event).filter(status=TicketStatus.VALID)


def get_all_tickets() -> QuerySet[Ticket]:
    return (
        Ticket.objects
        .all()
        .select_related("registration", "registration__event", "ticket_type")
        .order_by("-issued_at")
    )


def get_tickets_for_user(user) -> QuerySet[Ticket]:
    """
    Tickets visibles par un utilisateur.

    - Admin : tous
    - Organisateur : ses tickets + ceux de ses événements
    - Participant : ses tickets
    """
    if not user or not user.is_authenticated:
        return Ticket.objects.none()

    if user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN):
        return get_all_tickets()

    from apps.accounts.constants import ROLE_ORGANIZER
    if user.has_role(ROLE_ORGANIZER):
        return (
            Ticket.objects
            .filter(
                Q(registration__participant=user)
                | Q(registration__event__organizer=user)
            )
            .select_related("registration", "registration__event", "ticket_type")
            .distinct()
            .order_by("-issued_at")
        )

    return get_user_tickets(user)


# ==================================================================
# STATISTIQUES
# ==================================================================
def get_ticket_statistics(event) -> dict:
    """
    Statistiques des tickets d'un événement.
    """
    qs = Ticket.objects.filter(registration__event=event)
    counts = qs.aggregate(
        total=Count("id"),
        valid=Count("id", filter=Q(status=TicketStatus.VALID)),
        used=Count("id", filter=Q(status=TicketStatus.USED)),
        expired=Count("id", filter=Q(status=TicketStatus.EXPIRED)),
        cancelled=Count("id", filter=Q(status=TicketStatus.CANCELLED)),
    )
    return {
        "total_tickets": counts["total"],
        "valid": counts["valid"],
        "used": counts["used"],
        "expired": counts["expired"],
        "cancelled": counts["cancelled"],
    }