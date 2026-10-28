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
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.constants import ALL_ROLES
from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.events.constants import EventFormat, EventStatus
from apps.registrations.constants import RegistrationStatus
from apps.supervision.constants import AuditAction, AuditEntity, AuditResult
from apps.supervision.dashboard_selectors import (
    get_alerts,
    get_dashboard_overview,
    get_platform_statistics,
)
from apps.supervision.filters import (
    AuditLogFilter,
    OrganizerFilter,
    SupervisionAttendanceFilter,
    SupervisionCategoryFilter,
    SupervisionEventFilter,
    SupervisionRegistrationFilter,
    SupervisionUserFilter,
)
from apps.supervision.permissions import IsSupervisionAdmin
from apps.supervision.selectors import (
    get_audit_log_by_id,
    get_audit_logs,
    get_organizer_by_id,
    get_organizers,
    get_supervision_attendances,
    get_supervision_categories,
    get_supervision_category_by_id,
    get_supervision_event_detail,
    get_supervision_events,
    get_supervision_registration_by_id,
    get_supervision_registrations,
    get_supervision_user_detail,
    get_supervision_users,
    get_user_activity,
)
from apps.supervision.serializers import (
    AlertSerializer,
    AuditLogSerializer,
    DashboardSerializer,
    OrganizerSerializer,
    ReasonSerializer,
    StatisticsQuerySerializer,
    StatisticsSerializer,
    SupervisionAttendanceSerializer,
    SupervisionCategorySerializer,
    SupervisionCategoryWriteSerializer,
    SupervisionEventDetailSerializer,
    SupervisionEventSerializer,
    SupervisionRegistrationDetailSerializer,
    SupervisionRegistrationSerializer,
    SupervisionUserDetailSerializer,
    SupervisionUserSerializer,
    UserActivitySerializer,
)
from apps.supervision.services import (
    CategorySupervisionService,
    EventSupervisionService,
    UserSupervisionService,
)
from apps.supervision.throttles import SupervisionActionThrottle, SupervisionReadThrottle
from common.pagination.standard import StandardPagination
from common.responses.standard import APIResponse

TAG_AUDIT = ["Supervision — Audit"]
TAG_USERS = ["Supervision — Utilisateurs"]
TAG_ORGANIZERS = ["Supervision — Organisateurs"]
TAG_EVENTS = ["Supervision — Événements"]
TAG_CATEGORIES = ["Supervision — Catégories"]
TAG_REGISTRATIONS = ["Supervision — Inscriptions"]
TAG_ATTENDANCE = ["Supervision — Présences"]
TAG_DASHBOARD = ["Supervision — Tableau de bord"]

ERR_401 = OpenApiResponse(description="Authentification requise (jeton JWT manquant ou expiré).")
ERR_403 = OpenApiResponse(description="Accès réservé aux administrateurs.")
ERR_404 = OpenApiResponse(description="Ressource introuvable.")
ERR_429 = OpenApiResponse(description="Trop de requêtes : réessayez plus tard.")
ERR_400_FILTER = OpenApiResponse(description="Filtre invalide.")


# ==================================================================
# BASES COMMUNES
# ==================================================================
class SupervisionAPIView(APIView):
    """Base de TOUTES les vues de supervision."""

    permission_classes = [IsAuthenticated, IsSupervisionAdmin]

    def get_throttles(self):
        """
        Le débit dépend de la méthode HTTP, pas de la vue : une même route
        peut lire (GET, débit large) et agir (POST, PATCH, DELETE, débit
        strict), comme /categories/ ou /categories/{id}/.
        """
        if self.request.method in SAFE_METHODS:
            return [SupervisionReadThrottle()]
        return [SupervisionActionThrottle()]


def paginated_response(request, view, queryset, serializer_class, message):
    """Pagination standard EVENTFLOW (page_size max 50)."""
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    # La requête permet aux champs image de renvoyer une URL complète.
    serializer = serializer_class(page, many=True, context={"request": request})
    return APIResponse.success(
        data=paginator.get_paginated_response(serializer.data).data,
        message=message,
    )


def invalid_data(serializer):
    return APIResponse.error(
        message="Données invalides.",
        errors=serializer.errors,
        status_code=status.HTTP_400_BAD_REQUEST,
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
    serializer = ReasonSerializer(data=request.data)
    if not serializer.is_valid():
        return invalid_data(serializer)
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


class UserSuspendView(SupervisionAPIView):
    """POST /api/supervision/users/{id}/suspend/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Suspendre un compte",
        description=(
            "Désactive le compte (plus de connexion possible), révoque tous ses refresh "
            "tokens et enregistre l'action dans le journal d'audit. Raison obligatoire."
        ),
        request=ReasonSerializer,
        responses={200: SupervisionUserDetailSerializer, **_ACTION_ERRORS},
    )
    def post(self, request, pk):
        return _account_status_action(request, pk, UserSupervisionService.suspend, "Compte suspendu.")


class UserActivateView(SupervisionAPIView):
    """POST /api/supervision/users/{id}/activate/"""

    @extend_schema(
        tags=TAG_USERS,
        summary="Réactiver un compte",
        description="Réactive un compte suspendu. L'utilisateur devra se reconnecter. Raison obligatoire.",
        request=ReasonSerializer,
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


# ==================================================================
# ÉVÉNEMENTS (phase S3) — l'administrateur consulte et ANNULE
# ==================================================================
class SupervisionEventListView(SupervisionAPIView):
    """GET /api/supervision/events/"""

    @extend_schema(
        tags=TAG_EVENTS,
        summary="Liste des événements",
        description="Tous les événements, quel que soit leur statut (brouillons compris).",
        parameters=[
            OpenApiParameter("search", str, description="Titre ou e-mail de l'organisateur."),
            OpenApiParameter("status", str, enum=EventStatus.values),
            OpenApiParameter("format", str, enum=EventFormat.values),
            OpenApiParameter("organizer", str, description="UUID de l'organisateur."),
            OpenApiParameter("category", str, description="UUID de la catégorie."),
            OpenApiParameter("city", str),
            OpenApiParameter("starts_from", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("starts_to", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter(
                "ordering", str,
                description="start_at, created_at, title, registrations_confirmed (préfixe - : décroissant).",
            ),
        ],
        responses={200: SupervisionEventSerializer(many=True), 400: ERR_400_FILTER,
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = SupervisionEventFilter(request.GET, queryset=get_supervision_events())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(request, self, filterset.qs, SupervisionEventSerializer, "Liste des événements.")


class SupervisionEventDetailView(SupervisionAPIView):
    """GET /api/supervision/events/{id}/"""

    @extend_schema(
        tags=TAG_EVENTS,
        summary="Fiche d'un événement",
        description="Informations de l'événement et compteurs d'inscriptions et de présences.",
        responses={200: SupervisionEventDetailSerializer, 401: ERR_401, 403: ERR_403, 404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        event = get_supervision_event_detail(pk)
        if event is None:
            return not_found("Événement introuvable.")
        return APIResponse.success(
            data=SupervisionEventDetailSerializer(event, context={"request": request}).data,
            message="Fiche événement.",
        )


class SupervisionEventCancelView(SupervisionAPIView):
    """POST /api/supervision/events/{id}/cancel/"""

    @extend_schema(
        tags=TAG_EVENTS,
        summary="Annuler un événement (modération)",
        description=(
            "Annule un brouillon ou un événement publié. Raison obligatoire, "
            "enregistrée dans le journal d'audit. Un événement terminé ne peut "
            "pas être annulé. L'administrateur ne publie pas d'événement : "
            "c'est la décision de l'organisateur."
        ),
        request=ReasonSerializer,
        responses={
            200: SupervisionEventDetailSerializer,
            400: OpenApiResponse(description="Raison manquante, ou événement terminé."),
            401: ERR_401, 403: ERR_403, 404: ERR_404,
            409: OpenApiResponse(description="Événement déjà annulé."),
            429: ERR_429,
        },
    )
    def post(self, request, pk):
        serializer = ReasonSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_data(serializer)
        EventSupervisionService.cancel(
            actor=request.user,
            event_id=pk,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return APIResponse.success(
            data=SupervisionEventDetailSerializer(
                get_supervision_event_detail(pk), context={"request": request},
            ).data,
            message="Événement annulé.",
        )


# ==================================================================
# CATÉGORIES (phase S3)
# ==================================================================
class SupervisionCategoryListView(SupervisionAPIView):
    """GET / POST /api/supervision/categories/"""

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Liste des catégories",
        description="Toutes les catégories, actives ou désactivées, avec leur nombre d'événements.",
        parameters=[
            OpenApiParameter("search", str, description="Nom de la catégorie."),
            OpenApiParameter("is_active", bool),
            OpenApiParameter("ordering", str, description="name, created_at, events_total."),
        ],
        responses={200: SupervisionCategorySerializer(many=True), 400: ERR_400_FILTER,
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = SupervisionCategoryFilter(request.GET, queryset=get_supervision_categories())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(
            request, self, filterset.qs, SupervisionCategorySerializer, "Liste des catégories.",
        )

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Créer une catégorie",
        request=SupervisionCategoryWriteSerializer,
        responses={
            201: SupervisionCategorySerializer,
            400: OpenApiResponse(description="Nom manquant ou déjà utilisé."),
            401: ERR_401, 403: ERR_403,
            409: OpenApiResponse(description="Nom trop proche d'une catégorie existante."),
            429: ERR_429,
        },
    )
    def post(self, request):
        serializer = SupervisionCategoryWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_data(serializer)
        category = CategorySupervisionService.create(
            actor=request.user, validated_data=serializer.validated_data, request=request,
        )
        return APIResponse.created(
            data=SupervisionCategorySerializer(get_supervision_category_by_id(category.pk)).data,
            message="Catégorie créée.",
        )


class SupervisionCategoryDetailView(SupervisionAPIView):
    """GET / PATCH / DELETE /api/supervision/categories/{id}/"""

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Fiche d'une catégorie",
        responses={200: SupervisionCategorySerializer, 401: ERR_401, 403: ERR_403, 404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        category = get_supervision_category_by_id(pk)
        if category is None:
            return not_found("Catégorie introuvable.")
        return APIResponse.success(data=SupervisionCategorySerializer(category).data, message="Fiche catégorie.")

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Modifier une catégorie",
        description="Seuls les champs envoyés sont modifiés. L'avant / après est conservé dans l'audit.",
        request=SupervisionCategoryWriteSerializer,
        responses={
            200: SupervisionCategorySerializer,
            400: OpenApiResponse(description="Nom invalide ou déjà utilisé."),
            401: ERR_401, 403: ERR_403, 404: ERR_404,
            409: OpenApiResponse(description="Nom trop proche d'une catégorie existante."),
            429: ERR_429,
        },
    )
    def patch(self, request, pk):
        category = get_supervision_category_by_id(pk)
        if category is None:
            return not_found("Catégorie introuvable.")
        serializer = SupervisionCategoryWriteSerializer(category, data=request.data, partial=True)
        if not serializer.is_valid():
            return invalid_data(serializer)
        CategorySupervisionService.update(
            actor=request.user, category_id=pk,
            validated_data=serializer.validated_data, request=request,
        )
        return APIResponse.success(
            data=SupervisionCategorySerializer(get_supervision_category_by_id(pk)).data,
            message="Catégorie modifiée.",
        )

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Supprimer une catégorie",
        description=(
            "Uniquement si aucun événement ne l'utilise. Sinon, désactivez-la "
            "(POST categories/{id}/deactivate/)."
        ),
        responses={
            200: OpenApiResponse(description="Catégorie supprimée."),
            401: ERR_401, 403: ERR_403, 404: ERR_404,
            409: OpenApiResponse(description="Catégorie utilisée par au moins un événement."),
            429: ERR_429,
        },
    )
    def delete(self, request, pk):
        CategorySupervisionService.delete(actor=request.user, category_id=pk, request=request)
        return APIResponse.success(data=None, message="Catégorie supprimée.")


def _category_status_action(request, pk, active, success_message):
    serializer = ReasonSerializer(data=request.data)
    if not serializer.is_valid():
        return invalid_data(serializer)
    CategorySupervisionService.set_active(
        actor=request.user,
        category_id=pk,
        active=active,
        reason=serializer.validated_data["reason"],
        request=request,
    )
    return APIResponse.success(
        data=SupervisionCategorySerializer(get_supervision_category_by_id(pk)).data,
        message=success_message,
    )


_CATEGORY_STATUS_ERRORS = {
    400: OpenApiResponse(description="Raison manquante ou trop courte."),
    401: ERR_401, 403: ERR_403, 404: ERR_404,
    409: OpenApiResponse(description="La catégorie est déjà dans cet état."),
    429: ERR_429,
}


class SupervisionCategoryDeactivateView(SupervisionAPIView):
    """POST /api/supervision/categories/{id}/deactivate/"""

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Désactiver une catégorie",
        description="La catégorie disparaît des listes publiques ; ses événements ne sont pas modifiés.",
        request=ReasonSerializer,
        responses={200: SupervisionCategorySerializer, **_CATEGORY_STATUS_ERRORS},
    )
    def post(self, request, pk):
        return _category_status_action(request, pk, False, "Catégorie désactivée.")


class SupervisionCategoryActivateView(SupervisionAPIView):
    """POST /api/supervision/categories/{id}/activate/"""

    @extend_schema(
        tags=TAG_CATEGORIES,
        summary="Réactiver une catégorie",
        request=ReasonSerializer,
        responses={200: SupervisionCategorySerializer, **_CATEGORY_STATUS_ERRORS},
    )
    def post(self, request, pk):
        return _category_status_action(request, pk, True, "Catégorie réactivée.")


# ==================================================================
# INSCRIPTIONS (phase S4) — lecture seule
# ==================================================================
class SupervisionRegistrationListView(SupervisionAPIView):
    """GET /api/supervision/registrations/"""

    @extend_schema(
        tags=TAG_REGISTRATIONS,
        summary="Liste des inscriptions",
        description="Toutes les inscriptions de la plateforme, tous statuts. Lecture seule.",
        parameters=[
            OpenApiParameter("search", str, description="Référence, e-mail du participant ou titre de l'événement."),
            OpenApiParameter("status", str, enum=RegistrationStatus.values),
            OpenApiParameter("event", str, description="UUID de l'événement."),
            OpenApiParameter("participant", str, description="UUID du participant."),
            OpenApiParameter("registered_from", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("registered_to", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("ordering", str, description="registered_at, reference (préfixe - : décroissant)."),
        ],
        responses={200: SupervisionRegistrationSerializer(many=True), 400: ERR_400_FILTER,
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = SupervisionRegistrationFilter(request.GET, queryset=get_supervision_registrations())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(
            request, self, filterset.qs, SupervisionRegistrationSerializer, "Liste des inscriptions.",
        )


class SupervisionRegistrationDetailView(SupervisionAPIView):
    """GET /api/supervision/registrations/{id}/"""

    @extend_schema(
        tags=TAG_REGISTRATIONS,
        summary="Fiche d'une inscription",
        description="Participant, événement, organisateur et fiche de présence éventuelle.",
        responses={200: SupervisionRegistrationDetailSerializer, 401: ERR_401, 403: ERR_403,
                   404: ERR_404, 429: ERR_429},
    )
    def get(self, request, pk):
        registration = get_supervision_registration_by_id(pk)
        if registration is None:
            return not_found("Inscription introuvable.")
        return APIResponse.success(
            data=SupervisionRegistrationDetailSerializer(registration).data,
            message="Fiche inscription.",
        )


# ==================================================================
# PRÉSENCES (phase S4) — lecture seule
#   La liste d'accueil et les statistiques D'UN événement existent déjà
#   dans le module attendance (accessibles aux admins) :
#       GET /api/events/{id}/attendance/  et  .../attendance/stats/
#   Elles ne sont volontairement pas recopiées ici.
# ==================================================================
class SupervisionAttendanceListView(SupervisionAPIView):
    """GET /api/supervision/attendance/"""

    @extend_schema(
        tags=TAG_ATTENDANCE,
        summary="Présences, tous événements confondus",
        description=(
            "Toutes les fiches de présence (PRESENT / ABSENT). Pour la liste d'accueil "
            "complète d'un événement, utiliser GET /api/events/{id}/attendance/."
        ),
        parameters=[
            OpenApiParameter("search", str, description="E-mail du participant, référence ou titre de l'événement."),
            OpenApiParameter("status", str, enum=AttendanceStatus.values),
            OpenApiParameter("method", str, enum=CheckInMethod.values),
            OpenApiParameter("event", str, description="UUID de l'événement."),
            OpenApiParameter("participant", str, description="UUID du participant."),
            OpenApiParameter("checked_in_from", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("checked_in_to", str, description="AAAA-MM-JJ (inclus)."),
            OpenApiParameter("ordering", str, description="checked_in_at, created_at (préfixe - : décroissant)."),
        ],
        responses={200: SupervisionAttendanceSerializer(many=True), 400: ERR_400_FILTER,
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        filterset = SupervisionAttendanceFilter(request.GET, queryset=get_supervision_attendances())
        if not filterset.is_valid():
            return invalid_filters(filterset)
        return paginated_response(
            request, self, filterset.qs, SupervisionAttendanceSerializer, "Liste des présences.",
        )


# ==================================================================
# TABLEAU DE BORD, STATISTIQUES, ALERTES (phase S6)
# ==================================================================
class DashboardView(SupervisionAPIView):
    """GET /api/supervision/dashboard/"""

    @extend_schema(
        tags=TAG_DASHBOARD,
        summary="Tableau de bord",
        description="Chiffres clés de la plateforme, recalculés à chaque appel.",
        responses={200: DashboardSerializer, 401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        return APIResponse.success(
            data=DashboardSerializer(get_dashboard_overview()).data,
            message="Tableau de bord.",
        )


class StatisticsView(SupervisionAPIView):
    """GET /api/supervision/statistics/?months=12"""

    @extend_schema(
        tags=TAG_DASHBOARD,
        summary="Statistiques",
        description=(
            "Évolution mensuelle (nouveaux comptes, événements créés, inscriptions, "
            "arrivées) et répartitions par catégorie, ville, format et statut."
        ),
        parameters=[
            OpenApiParameter("months", int, description="Nombre de mois (1 à 24, défaut 12)."),
        ],
        responses={200: StatisticsSerializer, 400: OpenApiResponse(description="months invalide."),
                   401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        query = StatisticsQuerySerializer(data=request.GET)
        if not query.is_valid():
            return invalid_data(query)
        stats = get_platform_statistics(query.validated_data["months"])
        return APIResponse.success(data=StatisticsSerializer(stats).data, message="Statistiques.")


class AlertsView(SupervisionAPIView):
    """GET /api/supervision/alerts/"""

    @extend_schema(
        tags=TAG_DASHBOARD,
        summary="Alertes",
        description=(
            "Situations qui demandent l'attention d'un administrateur (refus de "
            "sécurité récents, événements terminés encore publiés, inscriptions en "
            "attente anciennes...). Seules les alertes déclenchées sont renvoyées, "
            "les plus graves d'abord."
        ),
        responses={200: AlertSerializer(many=True), 401: ERR_401, 403: ERR_403, 429: ERR_429},
    )
    def get(self, request):
        alerts = get_alerts()
        return APIResponse.success(
            data=AlertSerializer(alerts, many=True).data,
            message=f"{len(alerts)} alerte(s).",
        )
