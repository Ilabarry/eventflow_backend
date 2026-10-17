"""
Serializers du module Supervision.

Phase S1 : journal d'audit (lecture seule).
Phase S2 : utilisateurs, activité, organisateurs, raison des actions.

Règle : chaque serializer liste ses champs EXPLICITEMENT. Jamais de
fields = "__all__" : le mot de passe haché, les jetons ou tout champ
ajouté plus tard au modèle ne doivent pas sortir par accident.
"""

from rest_framework import serializers

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.events.models import Event
from apps.registrations.models import Registration
from apps.supervision.constants import REASON_MAX_LENGTH, REASON_MIN_LENGTH
from apps.supervision.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Entrée du journal d'audit.

    L'adresse IP et le navigateur sont des données personnelles : ils ne
    sont exposés QUE dans cette API, réservée aux administrateurs.
    """

    actor_id = serializers.UUIDField(source="actor.id", read_only=True, allow_null=True, default=None)
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    entity_type_label = serializers.CharField(source="get_entity_type_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "created_at",
            "actor_id",
            "actor_email",
            "action",
            "action_label",
            "entity_type",
            "entity_type_label",
            "entity_id",
            "description",
            "reason",
            "result",
            "metadata",
            "ip_address",
            "user_agent",
        )
        read_only_fields = fields


# ==================================================================
# ENTRÉE : raison d'une action sur un compte
# ==================================================================
class AccountStatusActionSerializer(serializers.Serializer):
    """POST users/{id}/suspend/ et users/{id}/activate/"""

    reason = serializers.CharField(
        min_length=REASON_MIN_LENGTH,
        max_length=REASON_MAX_LENGTH,
        trim_whitespace=True,
        help_text="Raison de l'action (obligatoire, conservée dans le journal d'audit).",
        error_messages={
            "required": "La raison est obligatoire.",
            "blank": "La raison est obligatoire.",
            "min_length": f"La raison doit contenir au moins {REASON_MIN_LENGTH} caractères.",
            "max_length": f"La raison ne doit pas dépasser {REASON_MAX_LENGTH} caractères.",
        },
    )


# ==================================================================
# SORTIE : utilisateurs
# ==================================================================
class SupervisionUserSerializer(serializers.ModelSerializer):
    """Ligne de la liste des utilisateurs (vue administrateur)."""

    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "roles",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_admin",
            "last_login",
            "created_at",
        )
        read_only_fields = fields

    # roles.all() utilise le prefetch_related du selector : aucune requête en plus.
    def get_roles(self, obj) -> list[str]:
        return sorted(role.name for role in obj.roles.all())

    def get_is_admin(self, obj) -> bool:
        return (
            obj.is_superuser
            or obj.is_staff
            or any(role.name == ROLE_ADMIN for role in obj.roles.all())
        )


class SupervisionUserDetailSerializer(SupervisionUserSerializer):
    """Fiche d'un utilisateur : la ligne de liste + ses compteurs."""

    organized_events_count = serializers.IntegerField(read_only=True)
    active_registrations_count = serializers.IntegerField(read_only=True)
    attendances_present_count = serializers.IntegerField(read_only=True)

    class Meta(SupervisionUserSerializer.Meta):
        fields = SupervisionUserSerializer.Meta.fields + (
            "updated_at",
            "organized_events_count",
            "active_registrations_count",
            "attendances_present_count",
        )
        read_only_fields = fields


# ==================================================================
# SORTIE : activité d'un utilisateur
# ==================================================================
class ActivityEventSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)

    class Meta:
        model = Event
        fields = ("id", "title", "status", "start_at", "end_at", "city", "category_name")
        read_only_fields = fields


class ActivityRegistrationSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField(source="event.id", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = Registration
        fields = ("id", "reference", "status", "registered_at", "event_id", "event_title")
        read_only_fields = fields


class ActivityAttendanceSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField(source="registration.event.id", read_only=True)
    event_title = serializers.CharField(source="registration.event.title", read_only=True)

    class Meta:
        model = Attendance
        fields = ("id", "status", "checked_in_at", "check_in_method", "event_id", "event_title")
        read_only_fields = fields


# Chaque rubrique = {"total": nombre réel, "recent": les plus récents}
class ActivityEventSection(serializers.Serializer):
    total = serializers.IntegerField()
    recent = ActivityEventSerializer(many=True)


class ActivityRegistrationSection(serializers.Serializer):
    total = serializers.IntegerField()
    recent = ActivityRegistrationSerializer(many=True)


class ActivityAttendanceSection(serializers.Serializer):
    total = serializers.IntegerField()
    recent = ActivityAttendanceSerializer(many=True)


class UserActivitySerializer(serializers.Serializer):
    organized_events = ActivityEventSection()
    registrations = ActivityRegistrationSection()
    attendances = ActivityAttendanceSection()


# ==================================================================
# SORTIE : organisateurs
# ==================================================================
class OrganizerSerializer(serializers.ModelSerializer):
    """Organisateur et ses compteurs (calculés en SQL par le selector)."""

    full_name = serializers.CharField(read_only=True)
    events_total = serializers.IntegerField(read_only=True)
    events_published = serializers.IntegerField(read_only=True)
    events_upcoming = serializers.IntegerField(read_only=True)
    events_cancelled = serializers.IntegerField(read_only=True)
    registrations_confirmed = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "is_active",
            "created_at",
            "last_login",
            "events_total",
            "events_published",
            "events_upcoming",
            "events_cancelled",
            "registrations_confirmed",
        )
        read_only_fields = fields
