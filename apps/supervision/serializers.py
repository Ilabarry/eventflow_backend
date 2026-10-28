"""
Serializers du module Supervision.

Phase S1 : journal d'audit (lecture seule).
Phase S2 : utilisateurs, activité, organisateurs, raison des actions.
Phase S3 : événements et catégories.
Phase S4 : inscriptions et présences (lecture seule).
Phase S6 : tableau de bord, statistiques, alertes (format des chiffres).

Règle : chaque serializer liste ses champs EXPLICITEMENT. Jamais de
fields = "__all__" : le mot de passe haché, les jetons ou tout champ
ajouté plus tard au modèle ne doivent pas sortir par accident.
"""

from rest_framework import serializers

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.attendance.constants import NOT_CHECKED_IN
from apps.attendance.models import Attendance
from apps.events.models import Category, Event
from apps.events.serializers import CategoryCreateSerializer
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.supervision.constants import (
    REASON_MAX_LENGTH,
    REASON_MIN_LENGTH,
    STATS_DEFAULT_MONTHS,
    STATS_MAX_MONTHS,
    AlertLevel,
)
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
# ENTRÉE : raison d'une action administrative
# ==================================================================
class ReasonSerializer(serializers.Serializer):
    """
    Corps {"reason": "..."} des actions sensibles : suspension et
    réactivation d'un compte, annulation d'un événement,
    désactivation et réactivation d'une catégorie.
    """

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


# ==================================================================
# SORTIE : événements (phase S3)
# ==================================================================
class SupervisionEventSerializer(serializers.ModelSerializer):
    """
    Événement vu par l'administrateur.

    Volontairement ABSENT : access_url (lien de connexion des événements
    en ligne), réservé aux participants inscrits.
    """

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    organizer_id = serializers.UUIDField(source="organizer.id", read_only=True)
    organizer_email = serializers.EmailField(source="organizer.email", read_only=True)
    organizer_name = serializers.CharField(source="organizer.full_name", read_only=True)
    category_id = serializers.UUIDField(source="category.id", read_only=True, default=None)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    registrations_confirmed = serializers.IntegerField(read_only=True)
    attendances_present = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "cover_image",
            "status",
            "status_label",
            "format",
            "participation_type",
            "start_at",
            "end_at",
            "city",
            "venue_name",
            "capacity_type",
            "capacity_limit",
            "organizer_id",
            "organizer_email",
            "organizer_name",
            "category_id",
            "category_name",
            "published_at",
            "created_at",
            "registrations_confirmed",
            "attendances_present",
        )
        read_only_fields = fields


class SupervisionEventDetailSerializer(SupervisionEventSerializer):
    registrations_pending = serializers.IntegerField(read_only=True)
    registrations_cancelled = serializers.IntegerField(read_only=True)

    class Meta(SupervisionEventSerializer.Meta):
        fields = SupervisionEventSerializer.Meta.fields + (
            "short_description",
            "updated_at",
            "registrations_pending",
            "registrations_cancelled",
        )
        read_only_fields = fields


# ==================================================================
# CATÉGORIES (phase S3)
# ==================================================================
class SupervisionCategorySerializer(serializers.ModelSerializer):
    """Catégorie vue par l'administrateur, avec ses compteurs."""

    events_total = serializers.IntegerField(read_only=True)
    events_published = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "is_active",
            "created_at",
            "updated_at",
            "events_total",
            "events_published",
        )
        read_only_fields = fields


class SupervisionCategoryWriteSerializer(CategoryCreateSerializer):
    """
    Création / modification d'une catégorie.

    On RÉUTILISE le serializer du module events (même règle d'unicité du
    nom). Seule différence : is_active n'est pas modifiable ici, car
    désactiver une catégorie passe par une action dédiée avec raison.
    """

    class Meta(CategoryCreateSerializer.Meta):
        fields = ("id", "name", "slug", "description", "icon")
        read_only_fields = ("id", "slug")


# ==================================================================
# SORTIE : inscriptions (phase S4)
# ==================================================================
class SupervisionRegistrationSerializer(serializers.ModelSerializer):
    """
    Une inscription vue par l'administrateur.

    attendance_status :
        PRESENT / ABSENT   → une fiche de présence existe ;
        NOT_CHECKED_IN     → inscription confirmée, pas encore de fiche ;
        null               → inscription en attente ou annulée
                             (le participant n'est pas attendu).
    """

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    participant_id = serializers.UUIDField(source="participant.id", read_only=True)
    participant_email = serializers.EmailField(source="participant.email", read_only=True)
    participant_name = serializers.CharField(source="participant.full_name", read_only=True)
    event_id = serializers.UUIDField(source="event.id", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_start_at = serializers.DateTimeField(source="event.start_at", read_only=True)
    event_status = serializers.CharField(source="event.status", read_only=True)
    attendance_status = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = (
            "id",
            "reference",
            "status",
            "status_label",
            "registered_at",
            "cancelled_at",
            "participant_id",
            "participant_email",
            "participant_name",
            "event_id",
            "event_title",
            "event_start_at",
            "event_status",
            "attendance_status",
        )
        read_only_fields = fields

    @staticmethod
    def _attendance(obj):
        # Relation inverse OneToOne : lève une exception s'il n'y a pas de
        # fiche ; getattr(..., None) renvoie None à la place.
        return getattr(obj, "attendance", None)

    def get_attendance_status(self, obj) -> str | None:
        attendance = self._attendance(obj)
        if attendance is not None:
            return attendance.status
        if obj.status == RegistrationStatus.CONFIRMED:
            return NOT_CHECKED_IN
        return None


class RegistrationAttendanceSerializer(serializers.ModelSerializer):
    """Fiche de présence affichée dans le détail d'une inscription."""

    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True, default=None)

    class Meta:
        model = Attendance
        fields = ("id", "status", "checked_in_at", "check_in_method", "recorded_by_email", "created_at")
        read_only_fields = fields


class SupervisionRegistrationDetailSerializer(SupervisionRegistrationSerializer):
    organizer_email = serializers.EmailField(source="event.organizer.email", read_only=True)
    attendance = serializers.SerializerMethodField()

    class Meta(SupervisionRegistrationSerializer.Meta):
        fields = SupervisionRegistrationSerializer.Meta.fields + (
            "organizer_email",
            "created_at",
            "updated_at",
            "attendance",
        )
        read_only_fields = fields

    def get_attendance(self, obj) -> dict | None:
        attendance = self._attendance(obj)
        return RegistrationAttendanceSerializer(attendance).data if attendance else None


# ==================================================================
# SORTIE : présences (phase S4)
# ==================================================================
class SupervisionAttendanceSerializer(serializers.ModelSerializer):
    registration_id = serializers.UUIDField(source="registration.id", read_only=True)
    registration_reference = serializers.CharField(source="registration.reference", read_only=True)
    participant_email = serializers.EmailField(source="registration.participant.email", read_only=True)
    participant_name = serializers.CharField(source="registration.participant.full_name", read_only=True)
    event_id = serializers.UUIDField(source="registration.event.id", read_only=True)
    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True, default=None)

    class Meta:
        model = Attendance
        fields = (
            "id",
            "status",
            "checked_in_at",
            "check_in_method",
            "recorded_by_email",
            "registration_id",
            "registration_reference",
            "participant_email",
            "participant_name",
            "event_id",
            "event_title",
            "created_at",
        )
        read_only_fields = fields


# ==================================================================
# PHASE S6 : tableau de bord
# Ces serializers décrivent le FORMAT des chiffres (pour Swagger et
# pour qu'Angular sache exactement quels champs il reçoit).
# ==================================================================
class DashboardUsersSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    suspended = serializers.IntegerField()
    participants = serializers.IntegerField()
    organizers = serializers.IntegerField()
    admins = serializers.IntegerField()
    new_last_30_days = serializers.IntegerField()


class DashboardEventsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    draft = serializers.IntegerField()
    published = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    upcoming = serializers.IntegerField(help_text="Publiés et pas encore commencés.")


class DashboardRegistrationsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    cancelled = serializers.IntegerField()


class DashboardAttendanceSerializer(serializers.Serializer):
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    expected = serializers.IntegerField(
        help_text="Inscriptions confirmées à des événements déjà commencés.",
    )
    attendance_rate = serializers.FloatField(help_text="present / expected x 100.")


class DashboardCategoriesSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()


class DashboardAuditSerializer(serializers.Serializer):
    actions_last_7_days = serializers.IntegerField()
    denied_last_7_days = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    users = DashboardUsersSerializer()
    events = DashboardEventsSerializer()
    registrations = DashboardRegistrationsSerializer()
    attendance = DashboardAttendanceSerializer()
    categories = DashboardCategoriesSerializer()
    audit = DashboardAuditSerializer()


# ==================================================================
# PHASE S6 : statistiques
# ==================================================================
class StatisticsQuerySerializer(serializers.Serializer):
    """Paramètre ?months= (entrée)."""

    months = serializers.IntegerField(
        required=False,
        default=STATS_DEFAULT_MONTHS,
        min_value=1,
        max_value=STATS_MAX_MONTHS,
        error_messages={
            "invalid": "months doit être un nombre entier.",
            "min_value": "months doit valoir au moins 1.",
            "max_value": f"months ne peut pas dépasser {STATS_MAX_MONTHS}.",
        },
    )


class MonthlyPointSerializer(serializers.Serializer):
    month = serializers.CharField(help_text="AAAA-MM")
    new_users = serializers.IntegerField()
    events_created = serializers.IntegerField()
    registrations = serializers.IntegerField()
    check_ins = serializers.IntegerField()


class CategoryCountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    events = serializers.IntegerField()


class CityCountSerializer(serializers.Serializer):
    city = serializers.CharField()
    events = serializers.IntegerField()


class FormatCountSerializer(serializers.Serializer):
    format = serializers.CharField()
    events = serializers.IntegerField()


class StatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    total = serializers.IntegerField()


class StatisticsSerializer(serializers.Serializer):
    months = serializers.IntegerField()
    since = serializers.DateField()
    monthly = MonthlyPointSerializer(many=True)
    events_by_category = CategoryCountSerializer(many=True)
    events_by_city = CityCountSerializer(many=True)
    events_by_format = FormatCountSerializer(many=True)
    registrations_by_status = StatusCountSerializer(many=True)


# ==================================================================
# PHASE S6 : alertes
# ==================================================================
class AlertSerializer(serializers.Serializer):
    code = serializers.CharField()
    level = serializers.ChoiceField(choices=AlertLevel.choices)
    message = serializers.CharField()
    count = serializers.IntegerField()
    samples = serializers.ListField(
        child=serializers.DictField(),
        help_text="Quelques exemples (5 au maximum) pour agir rapidement.",
    )
