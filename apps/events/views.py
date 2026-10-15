"""
Vues API du module Event.

Chaque vue est responsable d'UN endpoint. Elle :
    1. Reçoit la requête HTTP
    2. Valide via un serializer
    3. Appelle un service (logique métier)
    4. Retourne une réponse standardisée

Toutes les réponses utilisent APIResponse.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.constants import PERM_EVENT_CREATE, PERM_EVENT_PUBLISH
from apps.events.filters import EventFilter
from apps.events.models import Category, Event
from apps.events.pagination import EventPagination
from apps.events.permissions import IsEventOwnerOrAdmin
from apps.events.selectors import (
    get_active_categories,
    get_categories,
    get_category_by_id,
    get_event_by_id,
    get_events_for_user,
    get_organizer_events,
)
from apps.events.serializers import (
    CategoryCreateSerializer,
    CategorySerializer,
    EventCreateSerializer,
    EventDetailSerializer,
    EventListSerializer,
    EventOrganizerSerializer,
    EventShareSerializer,
    EventUpdateSerializer,
)
from apps.events.services import CategoryService, EventService
from common.exceptions.business import (
    CategoryAlreadyExists,
    CategoryInUse,
)
from common.permissions.base import IsAdmin, IsOrganizer
from common.responses.standard import APIResponse


# ==================================================================
# ÉVÉNEMENTS — Vues
# ==================================================================
class EventListCreateView(APIView):
    """
    GET  /api/events/    → Liste des événements visibles
    POST /api/events/    → Créer un événement (organisateur)

    GET  : accessible à tous. Les événements retournés dépendent
           du rôle de l'utilisateur (public / organisateur / admin).
    POST : accessible aux organisateurs et admins.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrganizer()]
        return [AllowAny()]

    def get(self, request):
        """Liste paginée avec filtres, recherche et tri."""
        # 1. Récupérer le queryset selon le rôle
        queryset = get_events_for_user(request.user)

        # 2. Appliquer les filtres
        filterset = EventFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Paginer
        paginator = EventPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)

        # 4. Sérialiser
        serializer = EventListSerializer(page, many=True, context={"request": request})

        # 5. Réponse paginée
        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Événements récupérés.",
        )

    def post(self, request):
        """Créer un événement (statut DRAFT par défaut)."""
        serializer = EventCreateSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        event = EventService.create_event(
            organizer=request.user,
            validated_data=serializer.validated_data,
        )

        return APIResponse.created(
            data=EventOrganizerSerializer(event, context={"request": request}).data,
            message="Événement créé avec succès (statut brouillon).",
        )


class EventDetailView(APIView):
    """
    GET    /api/events/{id}/    → Détail d'un événement
    PUT    /api/events/{id}/    → Modifier (propriétaire ou admin)
    PATCH  /api/events/{id}/    → Modifier partiellement
    DELETE /api/events/{id}/    → Supprimer (propriétaire ou admin)
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsEventOwnerOrAdmin()]

    def get(self, request, pk):
        """Détail d'un événement (public si PUBLISHED, privé sinon)."""
        event = get_event_by_id(pk)
        if not event:
            return APIResponse.error(
                message="Événement introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Vérifier l'accès
        is_owner = request.user.is_authenticated and event.organizer_id == request.user.id
        is_admin = request.user.is_authenticated and (
            request.user.is_superuser or request.user.is_staff
        )

        if event.status != "PUBLISHED" and not (is_owner or is_admin):
            return APIResponse.error(
                message="Cet événement n'est pas public.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Sérialiser selon le contexte
        if is_owner or is_admin:
            serializer = EventOrganizerSerializer(event, context={"request": request})
        else:
            serializer = EventDetailSerializer(event, context={"request": request})

        return APIResponse.success(
            data=serializer.data,
            message="Événement récupéré.",
        )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial: bool):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)

        serializer = EventUpdateSerializer(
            event, data=request.data, partial=partial, context={"request": request}
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        updated = EventService.update_event(
            event=event,
            validated_data=serializer.validated_data,
        )

        return APIResponse.success(
            data=EventOrganizerSerializer(updated, context={"request": request}).data,
            message="Événement mis à jour.",
        )

    def delete(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)

        EventService.delete_event(event=event)
        return APIResponse.success(
            data=None,
            message="Événement supprimé.",
        )


class MyEventsView(APIView):
    """
    GET /api/events/my/

    Liste les événements de l'organisateur connecté (tous statuts).
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    def get(self, request):
        queryset = get_organizer_events(request.user)

        filterset = EventFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = EventPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = EventOrganizerSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Vos événements.",
        )


class EventPublishView(APIView):
    """
    POST /api/events/{id}/publish/

    Publie un événement. Vérifie toutes les règles métier.
    """

    permission_classes = [IsAuthenticated, IsEventOwnerOrAdmin]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)

        event = EventService.publish_event(event=event)

        return APIResponse.success(
            data=EventOrganizerSerializer(event, context={"request": request}).data,
            message="Événement publié avec succès.",
        )


class EventCancelView(APIView):
    """
    POST /api/events/{id}/cancel/

    Annule un événement.
    """

    permission_classes = [IsAuthenticated, IsEventOwnerOrAdmin]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)

        event = EventService.cancel_event(event=event)

        return APIResponse.success(
            data=EventOrganizerSerializer(event, context={"request": request}).data,
            message="Événement annulé.",
        )


class EventShareView(APIView):
    """
    GET /api/events/{id}/share/

    Retourne les données de partage public d'un événement.
    Accessible à tous (uniquement pour les événements PUBLISHED).
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_event_by_id(pk)
        if not event or event.status != "PUBLISHED":
            return APIResponse.error(
                message="Événement introuvable ou non public.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = EventShareSerializer(event, context={"request": request})
        return APIResponse.success(
            data=serializer.data,
            message="Données de partage.",
        )


# ==================================================================
# CATÉGORIES — Vues
# ==================================================================
class CategoryListCreateView(APIView):
    """
    GET  /api/categories/    → Liste publique des catégories actives
    POST /api/categories/    → Créer une catégorie (admin uniquement)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdmin()]
        return [AllowAny()]

    def get(self, request):
        """Liste des catégories actives."""
        categories = get_active_categories()
        serializer = CategorySerializer(categories, many=True)
        return APIResponse.success(
            data=serializer.data,
            message="Catégories récupérées.",
        )

    def post(self, request):
        """Créer une catégorie (admin)."""
        serializer = CategoryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        category = CategoryService.create_category(validated_data=serializer.validated_data)

        return APIResponse.created(
            data=CategorySerializer(category).data,
            message="Catégorie créée.",
        )


class CategoryDetailView(APIView):
    """
    GET    /api/categories/{id}/    → Détail public
    PUT    /api/categories/{id}/    → Modifier (admin)
    PATCH  /api/categories/{id}/    → Modifier (admin)
    DELETE /api/categories/{id}/    → Supprimer (admin, si non utilisée)
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsAdmin()]

    def get(self, request, pk):
        category = get_category_by_id(pk)
        if not category:
            return APIResponse.error(
                message="Catégorie introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return APIResponse.success(
            data=CategorySerializer(category).data,
            message="Catégorie récupérée.",
        )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial: bool):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategoryCreateSerializer(
            category, data=request.data, partial=partial
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        updated = CategoryService.update_category(
            category=category,
            validated_data=serializer.validated_data,
        )
        return APIResponse.success(
            data=CategorySerializer(updated).data,
            message="Catégorie mise à jour.",
        )

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        CategoryService.delete_category(category=category)
        return APIResponse.success(
            data=None,
            message="Catégorie supprimée.",
        )