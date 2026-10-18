"""
Serializers du module Attendance.

Deux familles :
    - Entrée (ce qu'Angular envoie) : CheckInSerializer, MarkAbsentSerializer.
      Angular n'envoie QUE l'identifiant de l'inscription. L'événement,
      le participant, l'heure, la méthode et l'auteur sont déterminés
      par le backend : le frontend n'est jamais cru sur parole.
    - Sortie (ce que le backend renvoie) : un serializer par public,
      pour ne pas exposer plus que nécessaire.
"""

from rest_framework import serializers

from apps.attendance.constants import NOT_CHECKED_IN
from apps.attendance.models import Attendance
from apps.registrations.models import Registration


# ==================================================================
# ENTRÉE
# ==================================================================
class CheckInSerializer(serializers.Serializer):
    """POST /api/attendance/check-in/"""

    registration_id = serializers.UUIDField(
        help_text="Identifiant (UUID) de l'inscription du participant.",
    )


class MarkAbsentSerializer(serializers.Serializer):
    """POST /api/attendance/mark-absent/"""

    registration_id = serializers.UUIDField(
        help_text="Identifiant (UUID) de l'inscription du participant.",
    )


# ==================================================================
# SORTIE — Organisateur / administrateur
# ==================================================================
class AttendanceSerializer(serializers.ModelSerializer):
    """
    Présence vue par l'organisateur de l'événement ou un admin.

    Les informations du participant et de l'événement sont LUES depuis
    l'inscription (pas de duplication en base).
    """

    registration_id = serializers.UUIDField(source="registration.id", read_only=True)
    registration_reference = serializers.CharField(source="registration.reference", read_only=True)
    participant_name = serializers.CharField(source="registration.participant.full_name", read_only=True)
    participant_email = serializers.EmailField(source="registration.participant.email", read_only=True)
    event_id = serializers.UUIDField(source="registration.event.id", read_only=True)
    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = (
            "id",
            "status",
            "checked_in_at",
            "check_in_method",
            "registration_id",
            "registration_reference",
            "participant_name",
            "participant_email",
            "event_id",
            "event_title",
            "recorded_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_recorded_by_name(self, obj) -> str | None:
        return obj.recorded_by.full_name if obj.recorded_by else None


# ==================================================================
# SORTIE — Participant
# ==================================================================
class MyAttendanceSerializer(serializers.ModelSerializer):
    """
    Présence vue par le participant lui-même.

    On n'expose pas qui a fait le check-in : c'est une information
    interne à l'organisation.
    """

    registration_reference = serializers.CharField(source="registration.reference", read_only=True)
    event_id = serializers.UUIDField(source="registration.event.id", read_only=True)
    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    event_start_at = serializers.DateTimeField(source="registration.event.start_at", read_only=True)
    event_end_at = serializers.DateTimeField(source="registration.event.end_at", read_only=True)

    class Meta:
        model = Attendance
        fields = (
            "id",
            "status",
            "checked_in_at",
            "check_in_method",
            "registration_reference",
            "event_id",
            "event_title",
            "event_start_at",
            "event_end_at",
        )
        read_only_fields = fields


# ==================================================================
# SORTIE — Liste d'accueil d'un événement (organisateur)
# ==================================================================
class EventAttendanceRowSerializer(serializers.ModelSerializer):
    """
    Une ligne de la liste d'accueil = une inscription confirmée.

    attendance_status vaut PRESENT, ABSENT ou NOT_CHECKED_IN (calculé).
    registration_id permet à Angular d'appeler directement le check-in.
    """

    registration_id = serializers.UUIDField(source="id", read_only=True)
    registration_reference = serializers.CharField(source="reference", read_only=True)
    participant_name = serializers.CharField(source="participant.full_name", read_only=True)
    participant_email = serializers.EmailField(source="participant.email", read_only=True)
    attendance_id = serializers.SerializerMethodField()
    attendance_status = serializers.SerializerMethodField()
    checked_in_at = serializers.SerializerMethodField()
    check_in_method = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = (
            "registration_id",
            "registration_reference",
            "participant_name",
            "participant_email",
            "attendance_id",
            "attendance_status",
            "checked_in_at",
            "check_in_method",
        )
        read_only_fields = fields

    @staticmethod
    def _attendance(obj):
        # Accès à la relation inverse OneToOne : lève une exception
        # s'il n'y a pas de fiche, d'où ce getattr protégé.
        return getattr(obj, "attendance", None)

    def get_attendance_id(self, obj) -> str | None:
        attendance = self._attendance(obj)
        return str(attendance.id) if attendance else None

    def get_attendance_status(self, obj) -> str:
        attendance = self._attendance(obj)
        return attendance.status if attendance else NOT_CHECKED_IN

    def get_checked_in_at(self, obj) -> str | None:
        attendance = self._attendance(obj)
        if attendance and attendance.checked_in_at:
            return serializers.DateTimeField().to_representation(attendance.checked_in_at)
        return None

    def get_check_in_method(self, obj) -> str | None:
        attendance = self._attendance(obj)
        return attendance.check_in_method if attendance else None


# ==================================================================
# SORTIE — Statistiques (documentation Swagger et format de sortie)
# ==================================================================
class CheckInsByHourSerializer(serializers.Serializer):
    hour = serializers.DateTimeField()
    count = serializers.IntegerField()


class AttendanceStatsSerializer(serializers.Serializer):
    total_registered = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    not_checked_in = serializers.IntegerField()
    attendance_rate = serializers.FloatField()
    manual_check_ins = serializers.IntegerField()
    qr_check_ins = serializers.IntegerField()
    check_ins_by_hour = CheckInsByHourSerializer(many=True)


class QRCheckInSerializer(serializers.Serializer):
    """POST /api/attendance/check-in/qr/"""

    qr_code = serializers.CharField(
        max_length=500,
        help_text="Payload du QR code scanné (format: reference|signature).",
    )