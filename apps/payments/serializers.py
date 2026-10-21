"""
Serializers du module Payment.

Séparation stricte :
    - Lecture : PaymentSerializer, PaymentDetailSerializer, PaymentOrganizerSerializer
    - Écriture : InitiatePaymentSerializer, SimulatePaymentSerializer
    - Stats : PaymentStatsSerializer
"""

from rest_framework import serializers

from apps.payments.constants import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from apps.payments.models import Payment


# ==================================================================
# LECTURE — Participant
# ==================================================================
class PaymentSerializer(serializers.ModelSerializer):
    """Vue minimale d'un paiement (liste)."""

    event_title = serializers.CharField(source="registration.event.title", read_only=True)
    event_id = serializers.UUIDField(source="registration.event.id", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "transaction_reference",
            "amount",
            "currency",
            "payment_method",
            "provider",
            "status",
            "event_id",
            "event_title",
            "created_at",
            "paid_at",
        )
        read_only_fields = fields


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Vue détaillée d'un paiement (participant)."""

    registration_reference = serializers.CharField(
        source="registration.reference", read_only=True
    )
    event_title = serializers.CharField(source="registration.event.title", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "transaction_reference",
            "provider_reference",
            "registration_reference",
            "event_title",
            "amount",
            "currency",
            "payment_method",
            "provider",
            "status",
            "failure_code",
            "failure_message",
            "paid_at",
            "cancelled_at",
            "refunded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


# ==================================================================
# LECTURE — Organisateur
# ==================================================================
class PaymentOrganizerSerializer(serializers.ModelSerializer):
    """Vue d'un paiement côté organisateur (avec infos participant)."""

    participant_email = serializers.EmailField(
        source="registration.participant.email", read_only=True
    )
    participant_name = serializers.CharField(
        source="registration.participant.full_name", read_only=True
    )
    registration_reference = serializers.CharField(
        source="registration.reference", read_only=True
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "transaction_reference",
            "provider_reference",
            "registration_reference",
            "participant_email",
            "participant_name",
            "amount",
            "currency",
            "payment_method",
            "provider",
            "status",
            "created_at",
            "paid_at",
        )
        read_only_fields = fields


# ==================================================================
# ÉCRITURE — Initiation
# ==================================================================
class InitiatePaymentSerializer(serializers.Serializer):
    """
    Serializer pour initier un paiement.

    IMPORTANT : le montant n'est PAS fourni par le client.
    Le backend le calcule à partir de Event.base_price.
    """

    registration_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    provider = serializers.ChoiceField(choices=PaymentProvider.choices)

    def validate_registration_id(self, value):
        """Vérifie que la Registration existe et est payable."""
        from apps.registrations.models import Registration
        from apps.registrations.constants import RegistrationStatus

        try:
            registration = Registration.objects.select_related(
                "event", "participant"
            ).get(pk=value)
        except Registration.DoesNotExist:
            raise serializers.ValidationError("Inscription introuvable.")

        if registration.status != RegistrationStatus.PENDING:
            raise serializers.ValidationError(
                "Cette inscription n'est pas en attente de paiement."
            )

        self._registration = registration
        return value

    @property
    def registration(self):
        return self._registration


# ==================================================================
# ÉCRITURE — Simulation (développement)
# ==================================================================
class SimulatePaymentSerializer(serializers.Serializer):
    """Serializer pour simuler un résultat de paiement (dev)."""

    result = serializers.ChoiceField(
        choices=["SUCCESS", "FAILED", "CANCELLED", "PENDING"],
        help_text="Résultat à simuler.",
    )


# ==================================================================
# LECTURE — Statistiques
# ==================================================================
class PaymentStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques d'un événement."""

    total_transactions = serializers.IntegerField()
    successful = serializers.IntegerField()
    pending = serializers.IntegerField()
    failed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    refunded = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    refunded_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()