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
        serializer = ParticipantDashboardSerializer(instance=dashboard_data)

        return APIResponse.success(
            data=serializer.data,
            message="Dashboard participant récupéré.",
        )