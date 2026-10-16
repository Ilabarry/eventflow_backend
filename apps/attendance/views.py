"""
Vues API du module Attendance.

Les vues restent fines (même principe que registrations) :
    1. valider les données reçues (serializer) ;
    2. appeler le service ou le selector ;
    3. renvoyer une réponse au format standard EVENTFLOW (APIResponse).

Les erreurs métier levées par le service (403, 404, 409...) sont
converties automatiquement au format standard par le handler global
(common/exceptions/handlers.py) : aucun try/except n'est nécessaire ici.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.filters import EventAttendanceFilter
from apps.attendance.permissions import (
    CanViewAttendance,
    can_manage_event_attendance,
    can_view_registration_attendance,
)
from apps.attendance.selectors import (
    get_attendance_by_id,
    get_attendance_by_registration,
    get_event_attendance_list,
    get_event_attendance_stats,
    get_user_attendances,
)
from apps.attendance.serializers import (
    AttendanceSerializer,
    AttendanceStatsSerializer,
    CheckInSerializer,
    EventAttendanceRowSerializer,
    MarkAbsentSerializer,
    MyAttendanceSerializer,
)
from apps.attendance.services import AttendanceService
from apps.events.models import Event
from apps.registrations.models import Registration
from common.pagination.standard import StandardPagination
from common.responses.standard import APIResponse

TAG = ["Attendance"]

# Réponses d'erreur communes, pour la documentation Swagger
_ERR_400 = OpenApiResponse(description="Données invalides, inscription non éligible ou check-in fermé.")
_ERR_401 = OpenApiResponse(description="Authentification requise (jeton JWT manquant ou expiré).")
_ERR_403 = OpenApiResponse(description="Vous n'êtes pas l'organisateur de cet événement.")
_ERR_404 = OpenApiResponse(description="Inscription ou présence introuvable.")
_ERR_409 = OpenApiResponse(description="Participant déjà enregistré comme présent.")


def _invalid_data(serializer):
    """Réponse 400 standard pour un corps de requête invalide."""
    return APIResponse.error(
        message="Données invalides.",
        errors=serializer.errors,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


# ==================================================================
# ORGANISATEUR — Check-in manuel
# ==================================================================
class CheckInView(APIView):
    """POST /api/attendance/check-in/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Check-in manuel d'un participant",
        description=(
            "Enregistre la présence du participant lié à l'inscription. "
            "Réservé à l'organisateur de l'événement ou à un administrateur. "
            "L'événement est déduit de l'inscription côté serveur. "
            "Réponse au format standard : {success, message, data}."
        ),
        request=CheckInSerializer,
        responses={
            201: AttendanceSerializer,
            400: _ERR_400, 401: _ERR_401, 403: _ERR_403, 404: _ERR_404, 409: _ERR_409,
        },
    )
    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid_data(serializer)

        attendance = AttendanceService.check_in(
            registration_id=serializer.validated_data["registration_id"],
            performed_by=request.user,
        )
        return APIResponse.created(
            data=AttendanceSerializer(get_attendance_by_id(attendance.id)).data,
            message="Présence enregistrée avec succès.",
        )


# ==================================================================
# ORGANISATEUR — Déclarer un absent
# ==================================================================
class MarkAbsentView(APIView):
    """POST /api/attendance/mark-absent/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Déclarer un participant absent",
        description=(
            "Crée une fiche ABSENT pour l'inscription, après le début de l'événement. "
            "Appel idempotent : si le participant est déjà déclaré absent, "
            "la fiche existante est renvoyée. Refusé (409) s'il est présent."
        ),
        request=MarkAbsentSerializer,
        responses={
            200: AttendanceSerializer,
            400: _ERR_400, 401: _ERR_401, 403: _ERR_403, 404: _ERR_404, 409: _ERR_409,
        },
    )
    def post(self, request):
        serializer = MarkAbsentSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid_data(serializer)

        attendance = AttendanceService.mark_absent(
            registration_id=serializer.validated_data["registration_id"],
            performed_by=request.user,
        )
        return APIResponse.success(
            data=AttendanceSerializer(get_attendance_by_id(attendance.id)).data,
            message="Participant déclaré absent.",
        )


# ==================================================================
# PARTICIPANT — Mes présences
# ==================================================================
class MyAttendanceView(APIView):
    """GET /api/attendance/me/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Mes présences",
        description="Liste paginée des présences du participant connecté (?page=, ?page_size=).",
        responses={200: MyAttendanceSerializer(many=True), 401: _ERR_401},
    )
    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(get_user_attendances(request.user), request, view=self)
        serializer = MyAttendanceSerializer(page, many=True)
        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Mes présences.",
        )


# ==================================================================
# DÉTAIL D'UNE PRÉSENCE
# ==================================================================
class AttendanceDetailView(APIView):
    """GET /api/attendance/{id}/"""

    permission_classes = [IsAuthenticated, CanViewAttendance]

    @extend_schema(
        tags=TAG,
        summary="Détail d'une présence",
        description="Accessible au participant concerné, à l'organisateur de l'événement et aux administrateurs.",
        responses={200: AttendanceSerializer, 401: _ERR_401, 403: _ERR_403, 404: _ERR_404},
    )
    def get(self, request, pk):
        attendance = get_attendance_by_id(pk)
        if attendance is None:
            return APIResponse.error(
                message="Présence introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, attendance)

        # Le participant voit sa version réduite ; l'organisateur et l'admin, la version complète.
        if attendance.registration.participant_id == request.user.id:
            data = MyAttendanceSerializer(attendance).data
        else:
            data = AttendanceSerializer(attendance).data
        return APIResponse.success(data=data, message="Présence récupérée.")


# ==================================================================
# PRÉSENCE D'UNE INSCRIPTION
# ==================================================================
class RegistrationAttendanceView(APIView):
    """GET /api/registrations/{registration_id}/attendance/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Présence liée à une inscription",
        description=(
            "Renvoie {checked_in: bool, attendance: objet ou null}. "
            "attendance = null signifie : inscrit, aucune fiche de présence pour l'instant."
        ),
        responses={200: OpenApiResponse(description="Statut de présence de l'inscription."),
                   401: _ERR_401, 403: _ERR_403, 404: _ERR_404},
    )
    def get(self, request, registration_id):
        registration = (
            Registration.objects.select_related("event")
            .filter(pk=registration_id)
            .first()
        )
        if registration is None:
            return APIResponse.error(
                message="Inscription introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if not can_view_registration_attendance(request.user, registration):
            return APIResponse.error(
                message="Vous n'avez pas accès à cette inscription.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        attendance = get_attendance_by_registration(registration.id)
        if attendance is None:
            payload = None
        elif registration.participant_id == request.user.id:
            payload = MyAttendanceSerializer(attendance).data
        else:
            payload = AttendanceSerializer(attendance).data

        return APIResponse.success(
            data={
                "checked_in": bool(attendance and attendance.is_present),
                "attendance": payload,
            },
            message="Présence de l'inscription.",
        )


# ==================================================================
# ORGANISATEUR — Liste d'accueil et statistiques d'un événement
# ==================================================================
def _get_managed_event(request, event_id):
    """
    Charge l'événement (404 s'il n'existe pas) et vérifie que l'utilisateur
    en est l'organisateur ou un admin. Renvoie (event, réponse_erreur).
    """
    event = get_object_or_404(Event, pk=event_id)
    if not can_manage_event_attendance(request.user, event):
        return event, APIResponse.error(
            message="Vous n'êtes pas l'organisateur de cet événement.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return event, None


class EventAttendanceListView(APIView):
    """GET /api/events/{event_id}/attendance/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Liste d'accueil d'un événement",
        description=(
            "Tous les inscrits confirmés de l'événement avec leur statut de présence "
            "(PRESENT, ABSENT ou NOT_CHECKED_IN). Réservé à l'organisateur et aux admins. "
            "Liste paginée (?page=, ?page_size=)."
        ),
        parameters=[
            OpenApiParameter("search", str, description="Nom, prénom, e-mail ou référence d'inscription."),
            OpenApiParameter("status", str, enum=["PRESENT", "ABSENT", "NOT_CHECKED_IN"]),
            OpenApiParameter("method", str, enum=["MANUAL", "QR_CODE"]),
            OpenApiParameter("checked_in_after", str, description="Date/heure ISO 8601."),
            OpenApiParameter("checked_in_before", str, description="Date/heure ISO 8601."),
            OpenApiParameter(
                "ordering", str,
                description="last_name, first_name, checked_in_at, registered_at (préfixe - pour décroissant).",
            ),
        ],
        responses={200: EventAttendanceRowSerializer(many=True), 400: _ERR_400,
                   401: _ERR_401, 403: _ERR_403, 404: _ERR_404},
    )
    def get(self, request, event_id):
        event, error = _get_managed_event(request, event_id)
        if error:
            return error

        filterset = EventAttendanceFilter(request.GET, queryset=get_event_attendance_list(event))
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = EventAttendanceRowSerializer(page, many=True)
        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message=f"Liste d'accueil de '{event.title}'.",
        )


class EventAttendanceStatsView(APIView):
    """GET /api/events/{event_id}/attendance/stats/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Statistiques de présence d'un événement",
        description=(
            "Calculées sur les inscriptions confirmées : total_registered, present, absent, "
            "not_checked_in, attendance_rate (present / total x 100), répartition par méthode "
            "et arrivées par heure. Réservé à l'organisateur et aux admins."
        ),
        responses={200: AttendanceStatsSerializer, 401: _ERR_401, 403: _ERR_403, 404: _ERR_404},
    )
    def get(self, request, event_id):
        event, error = _get_managed_event(request, event_id)
        if error:
            return error

        stats = get_event_attendance_stats(event)
        return APIResponse.success(
            data=AttendanceStatsSerializer(stats).data,
            message=f"Statistiques de présence de '{event.title}'.",
        )
