"""
Serializers du module Certificates.

Séparation stricte :
    - Lecture participant : MyCertificateSerializer
    - Lecture organisateur : CertificateOrganizerSerializer
    - Vérification publique : CertificateVerifySerializer
    - Entrée : GenerateCertificateSerializer, RevokeCertificateSerializer
"""

from rest_framework import serializers

from apps.certificates.models import Certificate


# ==================================================================
# LECTURE — Participant
# ==================================================================
class MyCertificateSerializer(serializers.ModelSerializer):
    """Certificat vu par son propriétaire."""

    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    event_start_at = serializers.DateTimeField(source="registration.event.start_at", read_only=True)
    event_city = serializers.CharField(source="registration.event.city", read_only=True)
    registration_reference = serializers.CharField(source="registration.reference", read_only=True)
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "id",
            "reference",
            "status",
            "issued_at",
            "revoked_at",
            "registration_reference",
            "event_title",
            "event_start_at",
            "event_city",
            "verification_url",
        )
        read_only_fields = fields

    def get_verification_url(self, obj) -> str:
        from apps.certificates.qr import build_verify_url
        return build_verify_url(obj.verification_code)


# ==================================================================
# LECTURE — Organisateur
# ==================================================================
class CertificateOrganizerSerializer(serializers.ModelSerializer):
    """Certificat vu par l'organisateur."""

    participant_name = serializers.CharField(
        source="registration.participant.full_name", read_only=True
    )
    participant_email = serializers.EmailField(
        source="registration.participant.email", read_only=True
    )
    registration_reference = serializers.CharField(
        source="registration.reference", read_only=True
    )
    has_pdf = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "id",
            "reference",
            "status",
            "issued_at",
            "revoked_at",
            "registration_reference",
            "participant_name",
            "participant_email",
            "has_pdf",
        )
        read_only_fields = fields

    def get_has_pdf(self, obj) -> bool:
        return bool(obj.pdf_file)


# ==================================================================
# VÉRIFICATION PUBLIQUE
# ==================================================================
class CertificateVerifySerializer(serializers.Serializer):
    """Réponse de la vérification publique."""

    valid = serializers.BooleanField()
    reference = serializers.CharField(required=False)
    participant_name = serializers.CharField(required=False)
    event_title = serializers.CharField(required=False)
    event_date = serializers.DateField(required=False)
    issued_at = serializers.DateTimeField(required=False)
    status = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)


# ==================================================================
# ENTRÉE — Génération
# ==================================================================
class GenerateCertificateSerializer(serializers.Serializer):
    """POST /api/certificates/generate/"""

    registration_id = serializers.UUIDField(
        help_text="UUID de l'inscription.",
    )


# ==================================================================
# ENTRÉE — Révocation
# ==================================================================
class RevokeCertificateSerializer(serializers.Serializer):
    """PATCH /api/certificates/{id}/revoke/"""

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Raison optionnelle de la révocation (interne).",
    )


# ==================================================================
# STATISTIQUES
# ==================================================================
class CertificateStatsSerializer(serializers.Serializer):
    total_registered = serializers.IntegerField()
    issued = serializers.IntegerField()
    revoked = serializers.IntegerField()
    pending = serializers.IntegerField()
    not_generated = serializers.IntegerField()