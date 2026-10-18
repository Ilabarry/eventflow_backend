"""
Serializers du module Registration.

On utilise plusieurs serializers spécialisés :
    - RegistrationCreateSerializer       : POST (participant)
    - RegistrationListSerializer         : GET liste (mes inscriptions)
    - RegistrationDetailSerializer       : GET détail (participant)
    - RegistrationOrganizerSerializer    : GET liste côté organisateur
    - RegistrationOrganizerDetailSerializer : GET détail côté organisateur
    - RegistrationCancelSerializer       : cancel (body vide)
    - RegistrationConfirmSerializer      : confirm (organisateur, futur)
"""

from rest_framework import serializers

from apps.events.serializers import EventListSerializer
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.registrations.validators import (
    validate_event_is_open,
    validate_participation_type,
)


# ==================================================================
# SERIALIZER : Création
# ==================================================================
class RegistrationCreateSerializer(serializers.Serializer):
    """
    Serializer pour créer une inscription.

    Le participant reçoit :
        - event_id (UUID, obligatoire)
        - ticket_type_id (UUID, optionnel — obligatoire pour PAID)

    Le backend attribue automatiquement :
        - participant (request.user)
        - reference (généré)
        - status (CONFIRMED ou PENDING selon le type)
        - registered_at (now)
    """

    event_id = serializers.UUIDField()
    ticket_type_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="UUID du type de ticket (obligatoire pour événement payant).",
    )

    def validate(self, attrs: dict) -> dict:
        """
        Valide l'ensemble des données :
            1. Récupère l'événement.
            2. Vérifie qu'il accepte les inscriptions.
            3. Récupère le ticket_type (si fourni).
            4. Vérifie la cohérence PAID/FREE.
        """
        from apps.events.models import Event
        from apps.tickets.models import TicketType

        event_id = attrs.get("event_id")
        ticket_type_id = attrs.get("ticket_type_id")

        # 1. Récupérer l'événement
        try:
            event = Event.objects.select_related("organizer").get(pk=event_id)
        except Event.DoesNotExist:
            raise serializers.ValidationError(
                {"event_id": "Événement introuvable."}
            )

        # 2. Vérifier que l'événement accepte les inscriptions
        try:
            validate_event_is_open(event)
        except Exception as e:
            raise serializers.ValidationError(
                {"event_id": str(e)}
            )

        # 3. Récupérer le ticket_type si fourni
        ticket_type = None
        if ticket_type_id:
            try:
                ticket_type = TicketType.objects.get(
                    pk=ticket_type_id,
                    event=event,
                )
            except TicketType.DoesNotExist:
                raise serializers.ValidationError(
                    {"ticket_type_id": "Type de ticket introuvable pour cet événement."}
                )

        # 4. Vérifier la cohérence PAID/FREE
        try:
            validate_participation_type(event, ticket_type=ticket_type)
        except Exception as e:
            raise serializers.ValidationError(
                {"ticket_type_id": str(e)}
            )

        # Stocker pour la couche service
        attrs["_event"] = event
        attrs["_ticket_type"] = ticket_type
        return attrs

    @property
    def event(self):
        return self.validated_data["_event"]

    @property
    def ticket_type(self):
        return self.validated_data["_ticket_type"]


# ==================================================================
# SERIALIZER : Liste (participant)
# ==================================================================
class RegistrationListSerializer(serializers.ModelSerializer):
    """Liste des inscriptions du participant connecté."""

    event = EventListSerializer(read_only=True)

    class Meta:
        model = Registration
        fields = (
            "id",
            "reference",
            "status",
            "registered_at",
            "cancelled_at",
            "event",
        )
        read_only_fields = fields


# ==================================================================
# SERIALIZER : Détail (participant)
# ==================================================================
class RegistrationDetailSerializer(serializers.ModelSerializer):
    """
    Détail d'une inscription côté participant.

    Inclut :
        - Les données de l'événement
        - L'access_url SI l'inscription est CONFIRMED (participant attendu)
    """

    event = serializers.SerializerMethodField()
    ticket_type_name = serializers.CharField(
        source="ticket_type.name", read_only=True, default=None
    )

    class Meta:
        model = Registration
        fields = (
            "id",
            "reference",
            "status",
            "registered_at",
            "cancelled_at",
            "event",
            "ticket_type_name",
        )
        read_only_fields = fields

    def get_event(self, obj: Registration) -> dict:
        from apps.events.serializers import EventOrganizerSerializer

        if obj.status == RegistrationStatus.CONFIRMED:
            return EventOrganizerSerializer(
                obj.event, context=self.context
            ).data

        from apps.events.serializers import EventDetailSerializer
        return EventDetailSerializer(
            obj.event, context=self.context
        ).data


# ==================================================================
# SERIALIZER : Organisateur — Liste
# ==================================================================
class RegistrationOrganizerSerializer(serializers.ModelSerializer):
    """
    Inscription vue par l'organisateur.
    """

    participant_email = serializers.EmailField(source="participant.email", read_only=True)
    participant_name = serializers.CharField(source="participant.full_name", read_only=True)
    participant_phone = serializers.CharField(source="participant.phone", read_only=True)
    ticket_type_name = serializers.CharField(
        source="ticket_type.name", read_only=True, default=None
    )

    class Meta:
        model = Registration
        fields = (
            "id",
            "reference",
            "status",
            "registered_at",
            "cancelled_at",
            "participant_email",
            "participant_name",
            "participant_phone",
            "ticket_type_name",
        )
        read_only_fields = fields


# ==================================================================
# SERIALIZER : Organisateur — Détail
# ==================================================================
class RegistrationOrganizerDetailSerializer(RegistrationOrganizerSerializer):
    """
    Détail complet d'une inscription côté organisateur.
    """

    event = EventListSerializer(read_only=True)

    class Meta(RegistrationOrganizerSerializer.Meta):
        fields = RegistrationOrganizerSerializer.Meta.fields + ("event",)
        read_only_fields = fields


# ==================================================================
# SERIALIZER : Annulation
# ==================================================================
class RegistrationCancelSerializer(serializers.Serializer):
    """Serializer pour l'annulation d'une inscription."""

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Raison optionnelle de l'annulation (interne).",
    )


# ==================================================================
# SERIALIZER : Confirmation (organisateur)
# ==================================================================
class RegistrationConfirmSerializer(serializers.Serializer):
    """Serializer pour confirmer une inscription (organisateur)."""
    pass