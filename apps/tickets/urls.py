"""
Routes URL du module Tickets.
"""

from django.urls import path

from apps.tickets.views import (
    EventTicketTypeListCreateView,
    EventTicketsView,
    MyTicketsView,
    TicketCancelView,
    TicketDetailView,
    TicketListView,
    TicketTypeDetailView,
)

app_name = "tickets"

urlpatterns = [
    # TicketTypes (événement)
    path(
        "events/<uuid:event_id>/ticket-types/",
        EventTicketTypeListCreateView.as_view(),
        name="event-ticket-types",
    ),

    # TicketTypes (détail)
    path(
        "ticket-types/<uuid:pk>/",
        TicketTypeDetailView.as_view(),
        name="ticket-type-detail",
    ),

    # Tickets (participant)
    path("tickets/", TicketListView.as_view(), name="ticket-list"),
    path("tickets/my/", MyTicketsView.as_view(), name="ticket-my"),
    path("tickets/<uuid:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("tickets/<uuid:pk>/cancel/", TicketCancelView.as_view(), name="ticket-cancel"),

    # Tickets (organisateur)
    path(
        "events/<uuid:event_id>/tickets/",
        EventTicketsView.as_view(),
        name="event-tickets",
    ),
]