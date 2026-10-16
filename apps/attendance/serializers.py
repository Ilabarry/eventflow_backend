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

from apps.attendance.models import Attendance


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
