"""
Vues API du module Certificates.
"""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.certificates.filters import CertificateFilter
from apps.certificates.models import Certificate
from apps.certificates.permissions import (
    IsCertificateOwner,
    IsCertificateOwnerOrOrganizer,
    IsEventOrganizerOrAdmin,
)
from apps.certificates.selectors import (
    get_certificate_by_id,
    get_event_certificate_stats,
    get_event_certificates,
    get_user_certificates,
)
from apps.certificates.serializers import (
    CertificateOrganizerSerializer,
    CertificateStatsSerializer,
    CertificateVerifySerializer,
    GenerateCertificateSerializer,
    MyCertificateSerializer,
    RevokeCertificateSerializer,
)
from apps.certificates.services import CertificateService
from apps.events.models import Event
from apps.registrations.models import Registration
from common.pagination.standard import StandardPagination
from common.responses.standard import APIResponse

TAG = ["Certificates"]


# ==================================================================
# PARTICIPANT — Mes certificats
# ==================================================================
class MyCertificatesView(APIView):
    """GET /api/certificates/me/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Mes certificats",
        responses={200: MyCertificateSerializer(many=True)},
    )
    def get(self, request):
        qs = get_user_certificates(request.user)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = MyCertificateSerializer(page, many=True)

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Mes certificats.",
        )


# ==================================================================
# DÉTAIL
# ==================================================================
class CertificateDetailView(APIView):
    """GET /api/certificates/{id}/"""

    permission_classes = [IsAuthenticated, IsCertificateOwnerOrOrganizer]

    @extend_schema(tags=TAG, summary="Détail d'un certificat")
    def get(self, request, pk):
        certificate = get_certificate_by_id(pk)
        if not certificate:
            return APIResponse.error(
                message="Certificat introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, certificate)

        # Si participant → MySerializer ; si organisateur → OrganizerSerializer
        if certificate.registration.participant_id == request.user.id:
            data = MyCertificateSerializer(certificate).data
        else:
            data = CertificateOrganizerSerializer(certificate).data

        return APIResponse.success(data=data, message="Certificat récupéré.")


# ==================================================================
# TÉLÉCHARGEMENT PDF
# ==================================================================
class CertificateDownloadView(APIView):
    """GET /api/certificates/{id}/download/"""

    permission_classes = [IsAuthenticated, IsCertificateOwnerOrOrganizer]

    @extend_schema(tags=TAG, summary="Télécharger le PDF")
    def get(self, request, pk):
        certificate = get_object_or_404(Certificate, pk=pk)
        self.check_object_permissions(request, certificate)

        if not certificate.pdf_file:
            return APIResponse.error(
                message="Aucun PDF disponible pour ce certificat.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        try:
            response = FileResponse(
                certificate.pdf_file.open("rb"),
                content_type="application/pdf",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{certificate.reference}.pdf"'
            )
            return response
        except FileNotFoundError:
            raise Http404("Fichier PDF introuvable.")


# ==================================================================
# ORGANISATEUR — Génération
# ==================================================================
class GenerateCertificateView(APIView):
    """POST /api/certificates/generate/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Générer un certificat",
        request=GenerateCertificateSerializer,
        responses={201: CertificateOrganizerSerializer},
    )
    def post(self, request):
        serializer = GenerateCertificateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        registration = get_object_or_404(
            Registration,
            pk=serializer.validated_data["registration_id"],
        )

        # Vérifier que l'utilisateur est l'organisateur ou admin
        is_owner = registration.event.organizer_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff
        if not (is_owner or is_admin):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        certificate = CertificateService.generate_certificate(registration)

        return APIResponse.created(
            data=CertificateOrganizerSerializer(certificate).data,
            message="Certificat généré avec succès.",
        )


# ==================================================================
# RÉVOCATION
# ==================================================================
class RevokeCertificateView(APIView):
    """PATCH /api/certificates/{id}/revoke/"""

    permission_classes = [IsAuthenticated, IsEventOrganizerOrAdmin]

    @extend_schema(tags=TAG, summary="Révoquer un certificat")
    def patch(self, request, pk):
        certificate = get_object_or_404(Certificate, pk=pk)
        self.check_object_permissions(request, certificate)

        certificate = CertificateService.revoke_certificate(
            certificate=certificate,
            revoked_by=request.user,
        )

        return APIResponse.success(
            data=CertificateOrganizerSerializer(certificate).data,
            message="Certificat révoqué.",
        )


# ==================================================================
# VÉRIFICATION PUBLIQUE (sans auth, throttlée)
# ==================================================================
class VerifyCertificateThrottle(AnonRateThrottle):
    scope = "certificate_verify"


class VerifyCertificateView(APIView):
    """GET /api/certificates/verify/{verification_code}/"""

    permission_classes = [AllowAny]
    throttle_classes = [VerifyCertificateThrottle]

    @extend_schema(tags=TAG, summary="Vérification publique d'un certificat")
    def get(self, request, verification_code):
        try:
            certificate = CertificateService.verify_certificate(verification_code)
        except Exception:
            return APIResponse.success(
                data=CertificateVerifySerializer({
                    "valid": False,
                    "reason": "Certificat introuvable.",
                }).data,
                message="Certificat non trouvé.",
            )

        if certificate.is_revoked:
            return APIResponse.success(
                data=CertificateVerifySerializer({
                    "valid": False,
                    "reference": certificate.reference,
                    "reason": f"Ce certificat a été révoqué le {certificate.revoked_at.strftime('%d/%m/%Y')}.",
                }).data,
                message="Certificat révoqué.",
            )

        if not certificate.is_valid:
            return APIResponse.success(
                data=CertificateVerifySerializer({
                    "valid": False,
                    "reference": certificate.reference,
                    "reason": "Ce certificat n'est pas encore émis.",
                }).data,
                message="Certificat non valide.",
            )

        return APIResponse.success(
            data=CertificateVerifySerializer({
                "valid": True,
                "reference": certificate.reference,
                "participant_name": certificate.registration.participant.full_name,
                "event_title": certificate.registration.event.title,
                "event_date": certificate.registration.event.start_at.date(),
                "issued_at": certificate.issued_at,
                "status": certificate.status,
            }).data,
            message="Certificat valide.",
        )


# ==================================================================
# ORGANISATEUR — Liste des certificats d'un événement
# ==================================================================
class EventCertificatesView(APIView):
    """GET /api/events/{event_id}/certificates/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Certificats d'un événement")
    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        is_owner = event.organizer_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff
        if not (is_owner or is_admin):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        qs = get_event_certificates(event)

        filterset = CertificateFilter(request.GET, queryset=qs)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = CertificateOrganizerSerializer(page, many=True)

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message=f"Certificats de '{event.title}'.",
        )


# ==================================================================
# ORGANISATEUR — Statistiques
# ==================================================================
class EventCertificateStatsView(APIView):
    """GET /api/events/{event_id}/certificates/stats/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Statistiques des certificats")
    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        is_owner = event.organizer_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff
        if not (is_owner or is_admin):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        stats = get_event_certificate_stats(event)
        return APIResponse.success(
            data=CertificateStatsSerializer(stats).data,
            message=f"Statistiques de '{event.title}'.",
        )