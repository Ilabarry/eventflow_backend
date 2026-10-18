"""
Serializers du module Tickets.
"""

from rest_framework import serializers

from apps.tickets.models import Ticket, TicketType
from apps.tickets.services import TicketService
from apps.tickets.validators import (
    validate_sales_window,
    validate_ticket_type_can_be_modified,
    validate_ticket_type_price,
)


# ==================================================================
# TICKETTYPE — Création / Modification (organisateur)
# ==================================================================
class TicketTypeCreateSerializer(serializers.ModelSerializer):
    """Création d'un TicketType."""

    class Meta:
        model = TicketType
        fields = (
            "id", "name", "description",
            "price", "currency",
            "quantity_total",
            "sales_start_at", "sales_end_at",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        # Vérifier la période de vente
        validate_sales_window(
            attrs.get("sales_start_at"),
            attrs.get("sales_end_at"),
        )
        return attrs


class TicketTypeUpdateSerializer(serializers.ModelSerializer):
    """Modification d'un TicketType."""

    class Meta:
        model = TicketType
        fields = (
            "name", "description",
            "price", "currency",
            "quantity_total",
            "sales_start_at", "sales_end_at",
            "is_active",
        )

    def validate(self, attrs):
        validate_sales_window(
            attrs.get("sales_start_at", self.instance.sales_start_at),
            attrs.get("sales_end_at", self.instance.sales_end_at),
        )
        validate_ticket_type_can_be_modified(self.instance, attrs)
        return attrs


# ==================================================================
# TICKETTYPE — Lecture publique
# ==================================================================
class TicketTypePublicSerializer(serializers.ModelSerializer):
    """Vue publique d'un TicketType (participants)."""

    available_quantity = serializers.SerializerMethodField()
    is_sold_out = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketType
        fields = (
            "id", "name", "description",
            "price", "currency",
            "available_quantity", "is_sold_out",
            "sales_start_at", "sales_end_at",
        )

    def get_available_quantity(self, obj):
        return obj.available_quantity


# ==================================================================
# TICKETTYPE — Lecture organisateur
# ==================================================================
class TicketTypeOrganizerSerializer(serializers.ModelSerializer):
    """Vue complète d'un TicketType (organisateur)."""

    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = TicketType
        fields = (
            "id", "event", "name", "description",
            "price", "currency",
            "quantity_total", "quantity_sold",
            "available_quantity",
            "sales_start_at", "sales_end_at",
            "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_available_quantity(self, obj):
        return obj.available_quantity


# ==================================================================
# TICKET — Lecture participant
# ==================================================================
class TicketListSerializer(serializers.ModelSerializer):
    """Liste des tickets du participant."""

    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    event_id = serializers.UUIDField(source="registration.event.id", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True, default="Standard")

    class Meta:
        model = Ticket
        fields = (
            "id", "reference", "status",
            "issued_at", "used_at",
            "event_id", "event_title", "ticket_type_name",
        )
        read_only_fields = fields


class TicketDetailSerializer(serializers.ModelSerializer):
    """Détail d'un ticket (participant)."""

    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    event_start_at = serializers.DateTimeField(source="registration.event.start_at", read_only=True)
    event_end_at = serializers.DateTimeField(source="registration.event.end_at", read_only=True)
    event_venue = serializers.CharField(source="registration.event.venue_name", read_only=True, default="")
    event_city = serializers.CharField(source="registration.event.city", read_only=True, default="")
    event_format = serializers.CharField(source="registration.event.format", read_only=True)
    registration_reference = serializers.CharField(source="registration.reference", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True, default="Standard")
    qr_payload = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            "id", "reference", "status",
            "issued_at", "used_at", "cancelled_at",
            "registration_reference",
            "event_title", "event_start_at", "event_end_at",
            "event_venue", "event_city", "event_format",
            "ticket_type_name",
            "qr_payload",
        )
        read_only_fields = fields

    def get_qr_payload(self, obj):
        """Retourne le payload QR (sécurisé) pour le frontend."""
        return TicketService.generate_qr_payload(obj)


# ==================================================================
# TICKET — Lecture organisateur
# ==================================================================
class TicketOrganizerSerializer(serializers.ModelSerializer):
    """Vue d'un ticket côté organisateur."""

    participant_email = serializers.EmailField(source="registration.participant.email", read_only=True)
    participant_name = serializers.CharField(source="registration.participant.full_name", read_only=True)
    registration_reference = serializers.CharField(source="registration.reference", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True, default="Standard")

    class Meta:
        model = Ticket
        fields = (
            "id", "reference", "status",
            "issued_at", "used_at", "cancelled_at",
            "registration_reference",
            "participant_email", "participant_name",
            "ticket_type_name",
        )
        read_only_fields = fields