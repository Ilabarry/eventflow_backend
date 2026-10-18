"""
Serializers du module Event.

On utilise plusieurs serializers spécialisés (et non un seul géant) pour :
    - Contrôler précisément les champs exposés selon le contexte
    - Éviter les fuites de données (access_url, timestamps, etc.)
    - Faciliter la maintenance (chaque serializer a un rôle clair)

Liste :
    - CategorySerializer : lecture
    - CategoryCreateSerializer : création (admin)
    - EventCreateSerializer : création (organisateur)
    - EventUpdateSerializer : modification
    - EventListSerializer : liste publique (champs réduits)
    - EventDetailSerializer : détail public (sans access_url)
    - EventOrganizerSerializer : détail pour le propriétaire (avec access_url)
    - EventShareSerializer : données de partage
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.events.constants import (
    CapacityType,
    EventFormat,
    EventStatus,
    ParticipationType,
)
from apps.events.models import Category, Event
from apps.events.validators import (
    validate_capacity,
    validate_cover_image,
    validate_dates,
    validate_format_data,
)


# ==================================================================
# CATEGORY
# ==================================================================
class CategorySerializer(serializers.ModelSerializer):
    """Serializer de lecture pour une catégorie."""

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "icon", "is_active", "created_at")
        read_only_fields = fields


class CategoryCreateSerializer(serializers.ModelSerializer):
    """Serializer de création/modification de catégorie (admin uniquement)."""

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "icon", "is_active")
        read_only_fields = ("id", "slug")

    def validate_name(self, value: str) -> str:
        """Vérifie l'unicité du nom (insensible à la casse)."""
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Une catégorie avec ce nom existe déjà.")
        return value


# ==================================================================
# EVENT — Création
# ==================================================================
class EventCreateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la création d'un événement.

    Champs modifiables :
        - title, short_description, description, cover_image
        - format, participation_type, capacity_type, capacity_limit
        - start_at, end_at
        - venue_name, address, city, room (IN_PERSON)
        - online_platform, access_url (ONLINE)
        - category

    Champs NON modifiables (read_only) :
        - organizer (auto = user connecté)
        - status (auto = DRAFT)
        - published_at, created_at, updated_at
    """

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "short_description",
            "description",
            "cover_image",
            "format",
            "participation_type",
            "capacity_type",
            "capacity_limit",
            "base_price",
            "start_at",
            "end_at",
            "venue_name",
            "address",
            "city",
            "room",
            "online_platform",
            "access_url",
            "category",
        )
        read_only_fields = ("id",)

    # ------------------------------------------------------------------
    # Validations par champ
    # ------------------------------------------------------------------
    def validate_cover_image(self, value):
        if value:
            validate_cover_image(value)
        return value

    def validate(self, attrs: dict) -> dict:
        """Validations transverses (dépendent de plusieurs champs)."""
        # Dates
        start_at = attrs.get("start_at")
        end_at = attrs.get("end_at")
        if start_at and end_at:
            validate_dates(start_at, end_at)

        # Capacité
        capacity_type = attrs.get("capacity_type", CapacityType.UNLIMITED)
        capacity_limit = attrs.get("capacity_limit")
        validate_capacity(capacity_type, capacity_limit)

        # Format
        event_format = attrs.get("format", EventFormat.IN_PERSON)
        # À la création, on ne vérifie PAS les champs format (peut être un brouillon)
        # On le fera à la publication.

        return attrs


# ==================================================================
# EVENT — Modification
# ==================================================================
class EventUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la modification d'un événement.

    Toutes les validations de EventCreateSerializer s'appliquent.
    On empêche la modification de certains champs sensibles :
        - status (via les actions publish/cancel)
        - organizer
        - published_at
    """

    class Meta:
        model = Event
        fields = (
            "title",
            "short_description",
            "description",
            "cover_image",
            "format",
            "participation_type",
            "capacity_type",
            "capacity_limit",
            "base_price",
            "start_at",
            "end_at",
            "venue_name",
            "address",
            "city",
            "room",
            "online_platform",
            "access_url",
            "category",
        )

    def validate_cover_image(self, value):
        if value:
            validate_cover_image(value)
        return value

    def validate(self, attrs: dict) -> dict:
        """Validations transverses."""
        # Récupérer les valeurs (nouvelles OU existantes)
        start_at = attrs.get("start_at", self.instance.start_at)
        end_at = attrs.get("end_at", self.instance.end_at)
        if start_at and end_at:
            validate_dates(start_at, end_at)

        capacity_type = attrs.get("capacity_type", self.instance.capacity_type)
        capacity_limit = attrs.get("capacity_limit", self.instance.capacity_limit)
        validate_capacity(capacity_type, capacity_limit)

        return attrs


# ==================================================================
# EVENT — Liste publique (champs réduits)
# ==================================================================
class EventListSerializer(serializers.ModelSerializer):
    """
    Serializer pour la liste publique des événements.

    Champs réduits pour la performance (moins de données transférées).
    On n'expose PAS access_url ni les timestamps complets.
    """

    category = CategorySerializer(read_only=True)
    organizer = UserSerializer(read_only=True)
    available_slots = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "short_description",
            "cover_image",
            "format",
            "participation_type",
            "capacity_type",
            "start_at",
            "end_at",
            "city",
            "status",
            "category",
            "organizer",
            "available_slots",
        )

    def get_available_slots(self, obj: Event) -> int | None:
        """Retourne le nombre de places disponibles."""
        return obj.calculate_availability()


# ==================================================================
# EVENT — Détail public
# ==================================================================
class EventDetailSerializer(serializers.ModelSerializer):
    """
    Serializer pour le détail public d'un événement.

    IMPORTANT : on n'expose PAS access_url (lien privé).
    Ce champ n'est visible que pour le propriétaire et les inscrits.
    """

    category = CategorySerializer(read_only=True)
    organizer = UserSerializer(read_only=True)
    available_slots = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "short_description",
            "description",
            "cover_image",
            "format",
            "participation_type",
            "capacity_type",
            "capacity_limit",
            "start_at",
            "end_at",
            "venue_name",
            "address",
            "city",
            "room",
            "online_platform",
            # PAS d'access_url ici
            "status",
            "published_at",
            "category",
            "organizer",
            "available_slots",
            "created_at",
            "updated_at",
        )

    def get_available_slots(self, obj: Event) -> int | None:
        return obj.calculate_availability()


# ==================================================================
# EVENT — Détail pour l'organisateur (avec access_url)
# ==================================================================
class EventOrganizerSerializer(serializers.ModelSerializer):
    """
    Serializer pour le détail d'un événement côté organisateur.

    Inclut access_url (le propriétaire a le droit de le voir).
    Utilisé pour GET /api/events/{id}/ quand l'utilisateur est propriétaire.
    """

    category = CategorySerializer(read_only=True)
    available_slots = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "short_description",
            "description",
            "cover_image",
            "format",
            "participation_type",
            "capacity_type",
            "capacity_limit",
            "start_at",
            "end_at",
            "venue_name",
            "address",
            "city",
            "room",
            "online_platform",
            "access_url",  # ← Inclus pour le propriétaire
            "status",
            "published_at",
            "category",
            "available_slots",
            "created_at",
            "updated_at",
        )

    def get_available_slots(self, obj: Event) -> int | None:
        return obj.calculate_availability()


# ==================================================================
# EVENT — Partage
# ==================================================================
class EventShareSerializer(serializers.ModelSerializer):
    """
    Serializer pour le partage public d'un événement.

    Contient uniquement les données nécessaires au partage social :
        - URL publique
        - Titre
        - Description courte
        - Image
    """

    public_url = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "short_description",
            "cover_image",
            "start_at",
            "city",
            "public_url",
        )

    def get_public_url(self, obj: Event) -> str:
        """
        Construit l'URL publique de l'événement.

        Le frontend Angular utilisera cette URL pour le partage
        (ex: https://eventflow.sn/events/{id}).
        """
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/api/events/{obj.id}/")
        return f"/api/events/{obj.id}/"