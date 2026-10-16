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

    Le backend attribue automatiquement :
        - participant (request.user)
        - reference (généré)
        - status (CONFIRMED ou PENDING selon le type)
        - registered_at (now)
    """

    event_id = serializers.UUIDField()

    def validate_event_id(self, value):
        """Récupère l'événement et valide son éligibilité."""
        from apps.events.models import Event

        try:
            event = Event.objects.select_related("organizer").get(pk=value)
        except Event.DoesNotExist:
            raise serializers.ValidationError("Événement introuvable.")

        # Vérifier que l'événement accepte les inscriptions
        validate_event_is_open(event)

        # Vérifier que le type de participation est supporté
        validate_participation_type(event, ticket_type_id=None)

        # Stocker l'événement pour la couche service
        self._event = event
        return value

    @property
    def event(self):
        return self._event


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

    def get_event(self, obj: Registration) -> dict:
        """
        Retourne les détails de l'événement.

        Si l'inscription est CONFIRMED, on expose access_url
        (le participant est attendu).
        Sinon, on ne l'expose pas.
        """
        from apps.events.serializers import EventOrganizerSerializer

        # Le participant confirmé a le droit de voir access_url
        if obj.status == RegistrationStatus.CONFIRMED:
            return EventOrganizerSerializer(
                obj.event, context=self.context
            ).data

        # Sinon, détail public (sans access_url)
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

    Inclut des informations sur le participant (utile pour la gestion).
    """

    participant_email = serializers.EmailField(source="participant.email", read_only=True)
    participant_name = serializers.CharField(source="participant.full_name", read_only=True)
    participant_phone = serializers.CharField(source="participant.phone", read_only=True)

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
        )
        read_only_fields = fields


# ==================================================================
# SERIALIZER : Organisateur — Détail
# ==================================================================
class RegistrationOrganizerDetailSerializer(RegistrationOrganizerSerializer):
    """
    Détail complet d'une inscription côté organisateur.

    Identique à la liste, mais inclut les détails de l'événement.
    """

    event = EventListSerializer(read_only=True)

    class Meta(RegistrationOrganizerSerializer.Meta):
        fields = RegistrationOrganizerSerializer.Meta.fields + ("event",)
        read_only_fields = fields


# ==================================================================
# SERIALIZER : Annulation
# ==================================================================
class RegistrationCancelSerializer(serializers.Serializer):
    """
    Serializer pour l'annulation d'une inscription.

    Aucun champ n'est requis : le backend utilise l'ID de l'inscription
    passé dans l'URL.
    """

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
    """
    Serializer pour confirmer une inscription (organisateur).

    Aucun champ requis pour l'instant.
    """
    pass