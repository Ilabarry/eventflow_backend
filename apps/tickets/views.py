"""
Vues API du module Tickets.

Routes :
    - TicketType (organisateur) : CRUD
    - TicketType (public) : liste publique
    - Ticket (participant) : liste, détail, annulation
    - Ticket (organisateur) : liste des tickets d'un événement
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.events.models import Event
from apps.tickets.filters import TicketFilter, TicketTypeFilter
from apps.tickets.models import Ticket, TicketType
from apps.tickets.pagination import TicketPagination, TicketTypePagination
from apps.tickets.permissions import (
    IsTicketOwner,
    IsTicketOwnerOrEventOrganizer,
    IsTicketTypeOwner,
)
from apps.tickets.selectors import (
    get_available_ticket_types,
    get_event_ticket_types,
    get_event_tickets,
    get_ticket_by_id,
    get_ticket_type_by_id,
    get_tickets_for_user,
)
from apps.tickets.serializers import (
    TicketDetailSerializer,
    TicketListSerializer,
    TicketOrganizerSerializer,
    TicketTypeCreateSerializer,
    TicketTypeOrganizerSerializer,
    TicketTypePublicSerializer,
    TicketTypeUpdateSerializer,
)
from apps.tickets.services import TicketService, TicketTypeService
from common.responses.standard import APIResponse


# ==================================================================
# TICKETTYPE — Liste / Création (organisateur propriétaire)
# ==================================================================
class EventTicketTypeListCreateView(APIView):
    """
    GET  /api/events/{event_id}/ticket-types/  → public (actifs) OU organisateur
    POST /api/events/{event_id}/ticket-types/  → organisateur (propriétaire)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        # Si l'utilisateur est le propriétaire ou admin → vue complète
        is_owner = (
            request.user.is_authenticated
            and event.organizer_id == request.user.id
        )
        is_admin = (
            request.user.is_authenticated
            and (request.user.is_superuser or request.user.is_staff)
        )

        if is_owner or is_admin:
            qs = get_event_ticket_types(event)
            serializer_class = TicketTypeOrganizerSerializer
        else:
            qs = get_available_ticket_types(event)
            serializer_class = TicketTypePublicSerializer

        filterset = TicketTypeFilter(request.GET, queryset=qs)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = serializer_class(filterset.qs, many=True, context={"request": request})
        return APIResponse.success(
            data=serializer.data,
            message=f"Types de tickets de '{event.title}'.",
        )

    def post(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        # Vérifier que l'utilisateur est le propriétaire ou admin
        is_owner = event.organizer_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff
        if not (is_owner or is_admin):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = TicketTypeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        tt = TicketTypeService.create_ticket_type(
            event=event,
            validated_data=serializer.validated_data,
        )

        return APIResponse.created(
            data=TicketTypeOrganizerSerializer(tt, context={"request": request}).data,
            message="Type de ticket créé.",
        )


# ==================================================================
# TICKETTYPE — Détail / Modification / Suppression
# ==================================================================
class TicketTypeDetailView(APIView):
    """
    GET    /api/ticket-types/{id}/  → détail (propriétaire ou public)
    PATCH  /api/ticket-types/{id}/  → modifier (propriétaire)
    DELETE /api/ticket-types/{id}/  → supprimer (propriétaire, si non vendu)
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsTicketTypeOwner()]

    def get(self, request, pk):
        tt = get_ticket_type_by_id(pk)
        if not tt:
            return APIResponse.error(
                message="Type de ticket introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        is_owner = (
            request.user.is_authenticated
            and tt.event.organizer_id == request.user.id
        )
        is_admin = (
            request.user.is_authenticated
            and (request.user.is_superuser or request.user.is_staff)
        )

        if is_owner or is_admin:
            serializer = TicketTypeOrganizerSerializer(tt, context={"request": request})
        else:
            serializer = TicketTypePublicSerializer(tt, context={"request": request})

        return APIResponse.success(
            data=serializer.data,
            message="Type de ticket récupéré.",
        )

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def _update(self, request, pk, partial):
        tt = get_object_or_404(TicketType, pk=pk)
        self.check_object_permissions(request, tt)

        serializer = TicketTypeUpdateSerializer(tt, data=request.data, partial=partial)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        tt = TicketTypeService.update_ticket_type(
            ticket_type=tt,
            validated_data=serializer.validated_data,
        )
        return APIResponse.success(
            data=TicketTypeOrganizerSerializer(tt, context={"request": request}).data,
            message="Type de ticket mis à jour.",
        )

    def delete(self, request, pk):
        tt = get_object_or_404(TicketType, pk=pk)
        self.check_object_permissions(request, tt)

        TicketTypeService.delete_ticket_type(ticket_type=tt)
        return APIResponse.success(
            data=None,
            message="Type de ticket supprimé.",
        )


# ==================================================================
# TICKET — Liste / Mes tickets
# ==================================================================
class MyTicketsView(APIView):
    """GET /api/tickets/my/ → tickets du participant connecté."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.tickets.selectors import get_user_tickets
        qs = get_user_tickets(request.user)

        filterset = TicketFilter(request.GET, queryset=qs)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = TicketPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = TicketListSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Mes tickets.",
        )


class TicketListView(APIView):
    """
    GET /api/tickets/

    Liste des tickets visibles par l'utilisateur (auto-filtré).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_tickets_for_user(request.user)

        filterset = TicketFilter(request.GET, queryset=qs)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = TicketPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = TicketListSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Tickets récupérés.",
        )


# ==================================================================
# TICKET — Détail
# ==================================================================
class TicketDetailView(APIView):
    """GET /api/tickets/{id}/"""

    permission_classes = [IsAuthenticated, IsTicketOwnerOrEventOrganizer]

    def get(self, request, pk):
        ticket = get_ticket_by_id(pk)
        if not ticket:
            return APIResponse.error(
                message="Ticket introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, ticket)

        # Si l'utilisateur est organisateur ou admin → vue organisateur
        is_owner_ticket = ticket.registration.participant_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff

        if is_owner_ticket or is_admin:
            serializer = TicketDetailSerializer(ticket, context={"request": request})
        else:
            serializer = TicketOrganizerSerializer(ticket, context={"request": request})

        return APIResponse.success(
            data=serializer.data,
            message="Ticket récupéré.",
        )


# ==================================================================
# TICKET — Annulation
# ==================================================================
class TicketCancelView(APIView):
    """POST /api/tickets/{id}/cancel/"""

    permission_classes = [IsAuthenticated, IsTicketOwner]

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        self.check_object_permissions(request, ticket)

        ticket = TicketService.cancel_ticket(ticket=ticket)

        return APIResponse.success(
            data=TicketDetailSerializer(ticket, context={"request": request}).data,
            message="Ticket annulé.",
        )


# ==================================================================
# TICKET — Liste par événement (organisateur)
# ==================================================================
class EventTicketsView(APIView):
    """GET /api/events/{event_id}/tickets/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        is_admin = request.user.is_superuser or request.user.is_staff
        is_owner = event.organizer_id == request.user.id
        if not (is_admin or is_owner):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        qs = get_event_tickets(event)

        filterset = TicketFilter(request.GET, queryset=qs)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = TicketPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = TicketOrganizerSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message=f"Tickets de '{event.title}'.",
        )