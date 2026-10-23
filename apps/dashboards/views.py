from django.shortcuts import render

# Create your views here.
"""Vues API du module dashboards."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.dashboards.serializers import OrganizerDashboardSerializer
from apps.dashboards.services import OrganizerDashboardService
from common.permissions.base import IsOrganizer
from common.responses.standard import APIResponse

from apps.dashboards.serializers import ParticipantDashboardSerializer
from apps.dashboards.services import ParticipantDashboardService
from common.permissions.base import IsParticipant

from apps.dashboards.serializers import AdminDashboardSerializer
from apps.dashboards.services import AdminDashboardService
from common.permissions.base import IsAdmin

from apps.dashboards.serializers import (
    AdminStatisticsSerializer,
    OrganizerStatisticsSerializer,
)
from apps.dashboards.services import DashboardStatisticsService
from apps.dashboards.validators import (
    AdminStatisticsQuerySerializer,
    OrganizerStatisticsQuerySerializer,
)
class OrganizerDashboardView(APIView):
    """Dashboard en lecture seule de l'organisateur connecté."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    @extend_schema(
        summary="Récupérer le dashboard organisateur",
        description=(
            "Retourne les indicateurs et les prochains événements "
            "de l'organisateur authentifié."
        ),
        responses={200: OrganizerDashboardSerializer},
        tags=["Dashboards"],
    )
    def get(self, request):
        dashboard_data = OrganizerDashboardService.get_dashboard(
            user=request.user,
        )
        serializer = OrganizerDashboardSerializer(instance=dashboard_data)

        return APIResponse.success(
            data=serializer.data,
            message="Dashboard organisateur récupéré.",
        )
class ParticipantDashboardView(APIView):
    """Dashboard personnel du participant connecté."""

    permission_classes = [IsAuthenticated, IsParticipant]

    @extend_schema(
        summary="Récupérer le dashboard participant",
        description=(
            "Retourne les inscriptions et événements du participant "
            "authentifié, ainsi que la disponibilité des modules associés."
        ),
        responses={200: ParticipantDashboardSerializer},
        tags=["Dashboards"],
    )
    def get(self, request):
        dashboard_data = ParticipantDashboardService.get_dashboard(
            user=request.user,
        )
        # La requête permet à DRF de renvoyer l'URL complète de cover_image.
        serializer = ParticipantDashboardSerializer(
            instance=dashboard_data,
            context={"request": request},
        )

        return APIResponse.success(
            data=serializer.data,
            message="Dashboard participant récupéré.",
        )
class AdminDashboardView(APIView):
    """Dashboard global réservé aux administrateurs."""

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Récupérer le dashboard administrateur",
        description=(
            "Retourne les indicateurs globaux de la plateforme "
            "et les événements et utilisateurs récents."
        ),
        responses={200: AdminDashboardSerializer},
        tags=["Dashboards"],
    )
    def get(self, request):
        dashboard_data = AdminDashboardService.get_dashboard()
        serializer = AdminDashboardSerializer(instance=dashboard_data)

        return APIResponse.success(
            data=serializer.data,
            message="Dashboard administrateur récupéré.",
        )
class OrganizerStatisticsView(APIView):
    """Statistiques filtrees de l'organisateur connecte."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    @extend_schema(
        summary="Statistiques de l'organisateur",
        description=(
            "Retourne les tendances et repartitions des evenements et "
            "inscriptions de l'organisateur, selon les filtres fournis."
        ),
        parameters=[OrganizerStatisticsQuerySerializer],
        responses={200: OrganizerStatisticsSerializer},
        tags=["Dashboards"],
    )
    def get(self, request):
        query_serializer = OrganizerStatisticsQuerySerializer(
            data=request.query_params,
        )
        if not query_serializer.is_valid():
            return APIResponse.error(
                message="Parametres statistiques invalides.",
                errors=query_serializer.errors,
            )

        statistics = DashboardStatisticsService.get_organizer_statistics(
            user=request.user,
            filters=query_serializer.validated_data,
        )
        response_serializer = OrganizerStatisticsSerializer(
            instance=statistics,
        )

        return APIResponse.success(
            data=response_serializer.data,
            message="Statistiques organisateur recuperees.",
        )


class AdminStatisticsView(APIView):
    """Statistiques globales reservees aux administrateurs."""

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Statistiques administrateur",
        description=(
            "Retourne les tendances et repartitions globales de la plateforme "
            "pour une periode predefinie ou personnalisee."
        ),
        parameters=[AdminStatisticsQuerySerializer],
        responses={200: AdminStatisticsSerializer},
        tags=["Dashboards"],
    )
    def get(self, request):
        query_serializer = AdminStatisticsQuerySerializer(
            data=request.query_params,
        )
        if not query_serializer.is_valid():
            return APIResponse.error(
                message="Parametres statistiques invalides.",
                errors=query_serializer.errors,
            )

        statistics = DashboardStatisticsService.get_admin_statistics(
            filters=query_serializer.validated_data,
        )
        response_serializer = AdminStatisticsSerializer(
            instance=statistics,
        )

        return APIResponse.success(
            data=response_serializer.data,
            message="Statistiques administrateur recuperees.",
        )