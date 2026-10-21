"""
Vues API du module Registration.

Toutes les réponses utilisent APIResponse.
La logique métier est dans RegistrationService.
Ces vues restent fines : elles valident, appellent le service, retournent.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.events.models import Event
from apps.registrations.filters import RegistrationFilter
from apps.registrations.models import Registration
from apps.registrations.pagination import RegistrationPagination
from apps.registrations.permissions import (
    CanRegister,
    IsEventOrganizer,
    IsRegistrationOwnerOrEventOrganizer,
)
from apps.registrations.selectors import (
    get_event_registrations,
    get_registration_by_id,
    get_registrations_for_user,
)
from apps.registrations.serializers import (
    RegistrationCreateSerializer,
    RegistrationDetailSerializer,
    RegistrationListSerializer,
    RegistrationOrganizerDetailSerializer,
    RegistrationOrganizerSerializer,
)
from apps.registrations.services import RegistrationService
from common.responses.standard import APIResponse


# ==================================================================
# PARTICIPANT — Création et liste
# ==================================================================
class RegistrationListCreateView(APIView):
    """
    GET  /api/registrations/    → Mes inscriptions (auto-filtré)
    POST /api/registrations/    → S'inscrire à un événement
    """

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), CanRegister()]
        return [IsAuthenticated()]

    def get(self, request):
        """Liste des inscriptions visibles par l'utilisateur."""
        queryset = get_registrations_for_user(request.user)

        filterset = RegistrationFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = RegistrationPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = RegistrationListSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Inscriptions récupérées.",
        )

    def post(self, request):
        """Créer une inscription."""
        serializer = RegistrationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        registration = RegistrationService.create_registration(
            participant=request.user,
            event=serializer.event,
            ticket_type=serializer.ticket_type,  # ← AJOUT
        )

        return APIResponse.created(
            data=RegistrationDetailSerializer(registration, context={"request": request}).data,
            message="Inscription réussie.",
        )


class MyRegistrationsView(APIView):
    """
    GET /api/registrations/my/

    Alias explicite de la liste personnelle.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_registrations_for_user(request.user).filter(participant=request.user)

        filterset = RegistrationFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = RegistrationPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = RegistrationListSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Mes inscriptions.",
        )


# ==================================================================
# PARTICIPANT — Détail et annulation
# ==================================================================
class RegistrationDetailView(APIView):
    """
    GET /api/registrations/{id}/

    Détail d'une inscription.
    Accessible au propriétaire, à l'organisateur de l'événement, ou admin.
    """

    permission_classes = [IsAuthenticated, IsRegistrationOwnerOrEventOrganizer]

    def get(self, request, pk):
        registration = get_registration_by_id(pk)
        if not registration:
            return APIResponse.error(
                message="Inscription introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, registration)

        # Si l'utilisateur est l'organisateur, on utilise un serializer différent
        is_organizer = registration.event.organizer_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff

        if (is_organizer or is_admin) and registration.participant_id != request.user.id:
            serializer = RegistrationOrganizerDetailSerializer(registration, context={"request": request})
        else:
            serializer = RegistrationDetailSerializer(registration, context={"request": request})

        return APIResponse.success(
            data=serializer.data,
            message="Inscription récupérée.",
        )


class RegistrationCancelView(APIView):
    """
    POST /api/registrations/{id}/cancel/

    Annule une inscription.
    Accessible au propriétaire, à l'organisateur, ou admin.
    """

    permission_classes = [IsAuthenticated, IsRegistrationOwnerOrEventOrganizer]

    def post(self, request, pk):
        registration = get_object_or_404(Registration, pk=pk)
        self.check_object_permissions(request, registration)

        registration = RegistrationService.cancel_registration(
            registration=registration,
            cancelled_by_user=request.user,
        )

        return APIResponse.success(
            data=RegistrationDetailSerializer(registration, context={"request": request}).data,
            message="Inscription annulée.",
        )


# ==================================================================
# ORGANISATEUR — Inscriptions d'un événement
# ==================================================================
class EventRegistrationsView(APIView):
    """
    GET /api/events/{event_id}/registrations/

    Liste des inscriptions d'un événement.
    Accessible uniquement à l'organisateur propriétaire ou à un admin.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        # Vérifier que l'utilisateur est le propriétaire ou admin
        is_admin = request.user.is_superuser or request.user.is_staff
        is_owner = event.organizer_id == request.user.id
        if not (is_admin or is_owner):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        queryset = get_event_registrations(event)

        filterset = RegistrationFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = RegistrationPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = RegistrationOrganizerSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message=f"Inscriptions de '{event.title}'.",
        )


class EventRegistrationDetailView(APIView):
    """
    GET /api/events/{event_id}/registrations/{registration_id}/

    Détail d'une inscription d'un événement.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id, registration_id):
        event = get_object_or_404(Event, pk=event_id)

        is_admin = request.user.is_superuser or request.user.is_staff
        is_owner = event.organizer_id == request.user.id
        if not (is_admin or is_owner):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        registration = get_object_or_404(
            Registration, pk=registration_id, event=event
        )

        serializer = RegistrationOrganizerDetailSerializer(registration, context={"request": request})
        return APIResponse.success(
            data=serializer.data,
            message="Inscription récupérée.",
        )