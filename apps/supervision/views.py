"""
Vues API du module Supervision (préfixe /api/supervision/).

Toutes les vues héritent de SupervisionAPIView, qui impose :
    1. un jeton JWT valide (IsAuthenticated) ;
    2. un compte administrateur actif (IsSupervisionAdmin) ;
    3. une limitation du débit par utilisateur.
Une vue ne peut donc pas « oublier » une protection.
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.constants import ALL_ROLES
from apps.supervision.constants import AuditAction, AuditEntity, AuditResult
from apps.supervision.filters import AuditLogFilter, OrganizerFilter, SupervisionUserFilter
from apps.supervision.permissions import IsSupervisionAdmin
from apps.supervision.selectors import (
    get_audit_log_by_id,
    get_audit_logs,
    get_organizer_by_id,
    get_organizers,
    get_supervision_user_detail,
    get_supervision_users,
    get_user_activity,
)
from apps.supervision.serializers import (
    AccountStatusActionSerializer,
    AuditLogSerializer,
    OrganizerSerializer,
    SupervisionUserDetailSerializer,
    SupervisionUserSerializer,
    UserActivitySerializer,
)
from apps.supervision.services import UserSupervisionService
from apps.supervision.throttles import SupervisionActionThrottle, SupervisionReadThrottle
from common.pagination.standard import StandardPagination
from common.responses.standard import APIResponse

TAG_AUDIT = ["Supervision — Audit"]
TAG_USERS = ["Supervision — Utilisateurs"]
TAG_ORGANIZERS = ["Supervision — Organisateurs"]

ERR_401 = OpenApiResponse(description="Authentification requise (jeton JWT manquant ou expiré).")
ERR_403 = OpenApiResponse(description="Accès réservé aux administrateurs.")
ERR_404 = OpenApiResponse(description="Ressource introuvable.")
ERR_429 = OpenApiResponse(description="Trop de requêtes : réessayez plus tard.")
ERR_400_FILTER = OpenApiResponse(description="Filtre invalide.")


# ==================================================================
# BASES COMMUNES
# ==================================================================
class SupervisionAPIView(APIView):
    """Base de TOUTES les vues de supervision (lecture)."""

    permission_classes = [IsAuthenticated, IsSupervisionAdmin]
    throttle_classes = [SupervisionReadThrottle]


class SupervisionActionAPIView(SupervisionAPIView):
    """Base des vues d'ACTION (débit plus strict)."""

    throttle_classes = [SupervisionActionThrottle]


def paginated_response(request, view, queryset, serializer_class, message):
    """Pagination standard EVENTFLOW (page_size max 50)."""
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    serializer = serializer_class(page, many=True)
    return APIResponse.success(
        data=paginator.get_paginated_response(serializer.data).data,
        message=message,
    )


def not_found(message):
    return APIResponse.error(message=message, status_code=status.HTTP_404_NOT_FOUND)


def invalid_filters(filterset):
    return APIResponse.error(
        message="Paramètres de filtre invalides.",
        errors=filterset.errors,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


# ==================================================================
# JOURNAL D'AUDIT (lecture seule : seules les méthodes GET existent)
# ==================================================================
class AuditLogListView(SupervisionAPIView):
    """GET /api/supervision/audit-logs/"""

    @extend_schema(
        tags=TAG_AUDIT,
        summary="Journal d'audit",
        description=(
            "Liste paginée des actions administratives. Lecture seule : aucune "
            "entrée ne peut être créée, modifiée ou supprimée par l'API. "
            "Réservé aux administrateurs."
        ),
        parameters=[
            OpenApiParameter("action", str, enum=AuditAction.values),
            OpenApiParameter("entity_type", str, enum=AuditEntity.values),
            OpenApiParameter("entity_id", str),
            OpenApiParameter("actor", str, description="UUID de l'administrateur."),
            OpenApiParameter("result", str, enum=AuditResult.values),
            OpenApiParameter("date_from", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("date_to", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("search", str, description="E-mail de l'acteur, description ou raison."),
            OpenApiParameter("ordering", str, description="created_at ou action (préfixe - : décroissant)."),
        ],
        responses={200: AuditLogSerializer(many=True), 400: OpenApiResponse(description="Filtre invalide."),
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = AuditLogFilter(request.GET, queryset=get_audit_logs())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(request, self, filterset.qs, AuditLogSerializer, "Journal d'audit.")


class AuditLogDetailView(SupervisionAPIView):
    """GET /api/supervision/audit-logs/{id}/"""

    @extend_schema(
        tags=TAG_AUDIT,
        summary="Détail d'une entrée du journal d'audit",
        responses={200: AuditLogSerializer, 401: ERR_401, 403: ERR_403, 404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        entry = get_audit_log_by_id(pk)
        if entry is None:
            return APIResponse.error(
                message="Entrée d'audit introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return APIResponse.success(data=AuditLogSerializer(entry).data, message="Entrée d'audit.")


# ==================================================================
# UTILISATEURS (phase S2)
# ==================================================================
class UserListView(SupervisionAPIView):
    """GET /api/supervision/users/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Liste des utilisateurs",
        description="Tous les comptes de la plateforme, paginés et filtrables. Réservé aux administrateurs.",
        parameters=[
            OpenApiParameter("search", str, description="E-mail, prénom, nom ou téléphone."),
            OpenApiParameter("role", str, enum=list(ALL_ROLES)),
            OpenApiParameter("is_active", bool, description="false = comptes suspendus."),
            OpenApiParameter("joined_from", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("joined_to", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("ordering", str, description="created_at, last_name, email, last_login (préfixe - : décroissant)."),
        ],
        responses={200: SupervisionUserSerializer(many=True), 400: ERR_400_FILTER,
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = SupervisionUserFilter(request.GET, queryset=get_supervision_users())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(request, self, filterset.qs, SupervisionUserSerializer, "Liste des utilisateurs.")


class UserDetailView(SupervisionAPIView):
    """GET /api/supervision/users/{id}/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Fiche d'un utilisateur",
        description="Informations du compte et compteurs d'activité.",
        responses={200: SupervisionUserDetailSerializer, 401: ERR_401, 403: ERR_403, 404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        user = get_supervision_user_detail(pk)
        if user is None:
            return not_found("Utilisateur introuvable.")
        return APIResponse.success(data=SupervisionUserDetailSerializer(user).data, message="Fiche utilisateur.")


class UserActivityView(SupervisionAPIView):
    """GET /api/supervision/users/{id}/activity/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Activité d'un utilisateur",
        description=(
            "Événements organisés, inscriptions et présences de l'utilisateur : "
            "pour chaque rubrique, le total et les 10 éléments les plus récents."
        ),
        responses={200: UserActivitySerializer, 401: ERR_401, 403: ERR_403, 404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        user = get_supervision_users().filter(pk=pk).first()
        if user is None:
            return not_found("Utilisateur introuvable.")
        return APIResponse.success(
            data=UserActivitySerializer(get_user_activity(user)).data,
            message=f"Activité de {user.email}.",
        )


def _account_status_action(request, pk, service_action, success_message):
    """
    Partie commune à la suspension et à la réactivation :
        1. valider la raison ;
        2. appeler le service (garde-fous + modification + audit) ;
        3. renvoyer la fiche à jour.
    Les erreurs métier du service (403, 404, 409) sont converties
    automatiquement par le handler global.
    """
    serializer = AccountStatusActionSerializer(data=request.data)
    if not serializer.is_valid():
        return APIResponse.error(
            message="Données invalides.",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    service_action(
        actor=request.user,
        user_id=pk,
        reason=serializer.validated_data["reason"],
        request=request,
    )
    return APIResponse.success(
        data=SupervisionUserDetailSerializer(get_supervision_user_detail(pk)).data,
        message=success_message,
    )


_ACTION_ERRORS = {
    400: OpenApiResponse(description="Raison manquante ou trop courte."),
    401: ERR_401,
    403: OpenApiResponse(description="Garde-fou : auto-suspension, ou compte admin sans être super-admin."),
    404: ERR_404,
    409: OpenApiResponse(description="Déjà dans cet état, ou dernier administrateur actif."),
    429: ERR_429,
}


class UserSuspendView(SupervisionActionAPIView):
    """POST /api/supervision/users/{id}/suspend/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Suspendre un compte",
        description=(
            "Désactive le compte (plus de connexion possible), révoque tous ses refresh "
            "tokens et enregistre l'action dans le journal d'audit. Raison obligatoire."
        ),
        request=AccountStatusActionSerializer,
        responses={200: SupervisionUserDetailSerializer, **_ACTION_ERRORS},
    )
    def post(self, request, pk):
        return _account_status_action(request, pk, UserSupervisionService.suspend, "Compte suspendu.")


class UserActivateView(SupervisionActionAPIView):
    """POST /api/supervision/users/{id}/activate/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Réactiver un compte",
        description="Réactive un compte suspendu. L'utilisateur devra se reconnecter. Raison obligatoire.",
        request=AccountStatusActionSerializer,
        responses={200: SupervisionUserDetailSerializer, **_ACTION_ERRORS},
    )
    def post(self, request, pk):
        return _account_status_action(request, pk, UserSupervisionService.activate, "Compte réactivé.")


# ==================================================================
# ORGANISATEURS (phase S2)
# ==================================================================
class OrganizerListView(SupervisionAPIView):
    """GET /api/supervision/organizers/"""

    @extend_schema(
        tags=TAG_ORGANIZERS,
        summary="Liste des organisateurs",
        description="Comptes ayant le rôle organisateur, avec leurs compteurs d'événements et d'inscriptions.",
        parameters=[
            OpenApiParameter("search", str, description="E-mail, prénom, nom ou téléphone."),
            OpenApiParameter("is_active", bool),
            OpenApiParameter(
                "ordering", str,
                description="created_at, last_name, events_total, events_published, registrations_confirmed.",
            ),
        ],
        responses={200: OrganizerSerializer(many=True), 400: ERR_400_FILTER,
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = OrganizerFilter(request.GET, queryset=get_organizers())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(request, self, filterset.qs, OrganizerSerializer, "Liste des organisateurs.")


class OrganizerDetailView(SupervisionAPIView):
    """GET /api/supervision/organizers/{id}/"""

    @extend_schema(
        tags=TAG_ORGANIZERS,
        summary="Fiche d'un organisateur",
        responses={200: OrganizerSerializer, 401: ERR_401, 403: ERR_403, 404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        organizer = get_organizer_by_id(pk)
        if organizer is None:
            return not_found("Organisateur introuvable.")
        return APIResponse.success(data=OrganizerSerializer(organizer).data, message="Fiche organisateur.")
