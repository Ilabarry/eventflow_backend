"""
Routes URL du module Certificates.
"""

from django.urls import path

from apps.certificates.views import (
    CertificateDetailView,
    CertificateDownloadView,
    EventCertificateStatsView,
    EventCertificatesView,
    GenerateCertificateView,
    MyCertificatesView,
    RevokeCertificateView,
    VerifyCertificateView,
)

app_name = "certificates"

urlpatterns = [
    # Participant
    path("certificates/me/", MyCertificatesView.as_view(), name="certificate-my"),
    path("certificates/<uuid:pk>/", CertificateDetailView.as_view(), name="certificate-detail"),
    path("certificates/<uuid:pk>/download/", CertificateDownloadView.as_view(), name="certificate-download"),

    # Vérification publique
    path(
        "certificates/verify/<str:verification_code>/",
        VerifyCertificateView.as_view(),
        name="certificate-verify",
    ),

    # Génération / Révocation
    path("certificates/generate/", GenerateCertificateView.as_view(), name="certificate-generate"),
    path("certificates/<uuid:pk>/revoke/", RevokeCertificateView.as_view(), name="certificate-revoke"),

    # Organisateur
    path(
        "events/<uuid:event_id>/certificates/",
        EventCertificatesView.as_view(),
        name="event-certificates",
    ),
    path(
        "events/<uuid:event_id>/certificates/stats/",
        EventCertificateStatsView.as_view(),
        name="event-certificate-stats",
    ),
]