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

from apps.supervision.constants import AuditAction, AuditEntity, AuditResult
from apps.supervision.filters import AuditLogFilter
from apps.supervision.permissions import IsSupervisionAdmin
from apps.supervision.selectors import get_audit_log_by_id, get_audit_logs
from apps.supervision.serializers import AuditLogSerializer
from apps.supervision.throttles import SupervisionActionThrottle, SupervisionReadThrottle
from common.pagination.standard import StandardPagination
from common.responses.standard import APIResponse

TAG_AUDIT = ["Supervision — Audit"]

ERR_401 = OpenApiResponse(description="Authentification requise (jeton JWT manquant ou expiré).")
ERR_403 = OpenApiResponse(description="Accès réservé aux administrateurs.")
ERR_404 = OpenApiResponse(description="Ressource introuvable.")
ERR_429 = OpenApiResponse(description="Trop de requêtes : réessayez plus tard.")


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
