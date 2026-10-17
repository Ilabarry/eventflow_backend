"""Serializers de lecture pour les dashboards EVENTFLOW."""

from rest_framework import serializers

from apps.events.constants import CapacityType
from apps.events.models import Event
from apps.registrations.models import Registration
from apps.events.constants import EventFormat, EventStatus
from apps.registrations.constants import RegistrationStatus


class OrganizerDashboardSummarySerializer(serializers.Serializer):
    """Indicateurs synthétiques des événements et inscriptions."""

    total_events = serializers.IntegerField(read_only=True)
    published_events = serializers.IntegerField(read_only=True)
    upcoming_events = serializers.IntegerField(read_only=True)
    completed_events = serializers.IntegerField(read_only=True)
    draft_events = serializers.IntegerField(read_only=True)
    cancelled_events = serializers.IntegerField(read_only=True)

    total_registrations = serializers.IntegerField(read_only=True)
    active_registrations = serializers.IntegerField(read_only=True)
    pending_registrations = serializers.IntegerField(read_only=True)
    confirmed_registrations = serializers.IntegerField(read_only=True)
    cancelled_registrations = serializers.IntegerField(read_only=True)
    active_unique_participants = serializers.IntegerField(read_only=True)


class OrganizerEventCapacitySerializer(serializers.Serializer):
    """Capacité et occupation d'un événement organisateur."""

    type = serializers.CharField(source="capacity_type", read_only=True)
    limit = serializers.IntegerField(
        source="capacity_limit",
        allow_null=True,
        read_only=True,
    )
    occupied = serializers.IntegerField(
        source="active_registrations_count",
        read_only=True,
    )
    remaining = serializers.SerializerMethodField()
    fill_rate = serializers.SerializerMethodField()

    def get_remaining(self, event: Event) -> int | None:
        if event.capacity_type == CapacityType.UNLIMITED:
            return None

        if event.capacity_limit is None:
            return None

        return max(event.capacity_limit - event.active_registrations_count, 0)

    def get_fill_rate(self, event: Event) -> float | None:
        if (
            event.capacity_type == CapacityType.UNLIMITED
            or not event.capacity_limit
        ):
            return None

        return round(
            event.active_registrations_count / event.capacity_limit * 100,
            1,
        )


class OrganizerUpcomingEventSerializer(serializers.ModelSerializer):
    """Présentation légère d'un événement à venir."""

    pending_registrations_count = serializers.IntegerField(read_only=True)
    confirmed_registrations_count = serializers.IntegerField(read_only=True)
    capacity = OrganizerEventCapacitySerializer(source="*", read_only=True)

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "start_at",
            "end_at",
            "format",
            "participation_type",
            "city",
            "venue_name",
            "status",
            "pending_registrations_count",
            "confirmed_registrations_count",
            "capacity",
        )
        read_only_fields = fields


class OrganizerRegistrationEventSerializer(serializers.ModelSerializer):
    """Informations minimales sur l'événement lié à une inscription récente."""

    class Meta:
        model = Event
        fields = ("id", "title", "start_at")
        read_only_fields = fields


class OrganizerRecentRegistrationSerializer(serializers.ModelSerializer):
    """Inscription récente à l'un des événements de l'organisateur."""

    event = OrganizerRegistrationEventSerializer(read_only=True)
    participant_name = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = (
            "reference",
            "status",
            "registered_at",
            "participant_name",
            "event",
        )
        read_only_fields = fields

    def get_participant_name(self, registration: Registration) -> str:
        participant = registration.participant
        return f"{participant.first_name} {participant.last_name}".strip()


class OrganizerDashboardSerializer(serializers.Serializer):
    """Réponse read-only du dashboard organisateur."""

    summary = OrganizerDashboardSummarySerializer(read_only=True)
    upcoming_events = OrganizerUpcomingEventSerializer(
        many=True,
        read_only=True,
    )
    recent_registrations = OrganizerRecentRegistrationSerializer(
        many=True,
        read_only=True,
    )
    payment_statistics_available = serializers.BooleanField(read_only=True)
    financial_statistics = serializers.JSONField(
        allow_null=True,
        read_only=True,
     )
class ParticipantDashboardSummarySerializer(serializers.Serializer):
    """Indicateurs personnels du participant."""
    total_registrations = serializers.IntegerField(read_only=True)
    pending_registrations = serializers.IntegerField(read_only=True)
    confirmed_registrations = serializers.IntegerField(read_only=True)
    cancelled_registrations = serializers.IntegerField(read_only=True)
    upcoming_events = serializers.IntegerField(read_only=True)
    completed_events = serializers.IntegerField(read_only=True)
    attended_events = serializers.IntegerField(read_only=True)


class ParticipantDashboardAvailabilitySerializer(serializers.Serializer):
    """Indique quels modules peuvent alimenter le dashboard."""

    tickets = serializers.BooleanField(read_only=True)
    certificates = serializers.BooleanField(read_only=True)
    notifications = serializers.BooleanField(read_only=True)
    payments = serializers.BooleanField(read_only=True)


class ParticipantDashboardEventSerializer(serializers.ModelSerializer):
    """Informations événementielles non sensibles."""

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "start_at",
            "end_at",
            "format",
            "venue_name",
            "address",
            "city",
            "room",
            "online_platform",
            "status",
        )
        read_only_fields = fields


class ParticipantDashboardRegistrationSerializer(serializers.ModelSerializer):
    """Inscription personnelle et son événement."""

    event = ParticipantDashboardEventSerializer(read_only=True)
    access_url = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = (
            "id",
            "reference",
            "status",
            "registered_at",
            "event",
            "access_url",
        )
        read_only_fields = fields

    def get_access_url(self, registration: Registration) -> str | None:
        event = registration.event

        if (
            registration.status == RegistrationStatus.CONFIRMED
            and event.status == EventStatus.PUBLISHED
            and event.format == EventFormat.ONLINE
            and event.access_url
        ):
            return event.access_url

        return None


class ParticipantDashboardSerializer(serializers.Serializer):
    """Réponse read-only du dashboard participant."""

    summary = ParticipantDashboardSummarySerializer(read_only=True)
    upcoming_registrations = ParticipantDashboardRegistrationSerializer(
        many=True,
        read_only=True,
    )
    recent_registrations = ParticipantDashboardRegistrationSerializer(
        many=True,
        read_only=True,
    )
    availability = ParticipantDashboardAvailabilitySerializer(read_only=True)
    tickets = serializers.JSONField(allow_null=True, read_only=True)
    certificates = serializers.JSONField(allow_null=True, read_only=True)
    unread_notifications = serializers.IntegerField(
        allow_null=True,
        read_only=True,
    )
    recent_notifications = serializers.JSONField(
        allow_null=True,
        read_only=True,
    )