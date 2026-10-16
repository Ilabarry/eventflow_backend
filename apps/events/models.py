"""
Modèles du module Event : Event et Category.

Décisions clés :
    - UUID comme clé primaire (non devinable)
    - Enums via models.TextChoices (dans constants.py)
    - Index PostgreSQL sur les champs filtrés/triés fréquemment
    - Contraintes DB pour la cohérence (dates, capacité)
    - Pas de dépendance vers Registration (dépendance unidirectionnelle)
"""

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.events.constants import (
    ACCESS_URL_MAX_LENGTH,
    ADDRESS_MAX_LENGTH,
    ALLOWED_STATUS_TRANSITIONS,
    CITY_MAX_LENGTH,
    ONLINE_PLATFORM_MAX_LENGTH,
    ROOM_MAX_LENGTH,
    SHORT_DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    VENUE_NAME_MAX_LENGTH,
    CapacityType,
    EventFormat,
    EventStatus,
    ParticipationType,
)


# ==================================================================
# MODÈLE : Category
# ==================================================================
class Category(models.Model):
    """
    Catégorie d'événements (ex: Tech, Musique, Sport, Business...).
    
    Une catégorie ne peut pas être supprimée si elle est utilisée
    par au moins un événement (protection via on_delete=PROTECT).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom",
        help_text="Nom unique de la catégorie (ex: 'Tech').",
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        verbose_name="Slug",
        help_text="Identifiant URL-friendly généré automatiquement.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Icône",
        help_text="Nom d'icône (ex: 'tech', 'music') pour le frontend.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Si False, la catégorie n'apparaît plus dans les listes publiques.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour",
    )

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="idx_category_is_active"),
            models.Index(fields=["name"], name="idx_category_name"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Génère automatiquement le slug à partir du nom."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ==================================================================
# MODÈLE : Event
# ==================================================================
class Event(models.Model):
    """
    Événement créé par un organisateur.
    
    Règles métier principales :
        - organizer est le propriétaire (jamais modifiable via API)
        - Un événement commence toujours en DRAFT
        - capacity_limit est NULL si capacity_type=UNLIMITED
        - access_url n'est exposé qu'aux inscrits/propriétaire
        - start_at < end_at (contrainte DB)
    """

    # ------------------------------------------------------------------
    # Identifiant
    # ------------------------------------------------------------------
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_events",
        verbose_name="Organisateur",
        help_text="Utilisateur propriétaire de l'événement.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name="Catégorie",
        help_text="Une catégorie ne peut être supprimée si elle est utilisée.",
    )

    # ------------------------------------------------------------------
    # Informations principales
    # ------------------------------------------------------------------
    title = models.CharField(
        max_length=TITLE_MAX_LENGTH,
        verbose_name="Titre",
    )
    short_description = models.CharField(
        max_length=SHORT_DESCRIPTION_MAX_LENGTH,
        verbose_name="Description courte",
        help_text="Résumé affiché dans les listes et le partage social.",
    )
    description = models.TextField(
        verbose_name="Description complète",
    )
    cover_image = models.ImageField(
        upload_to="events/covers/",
        null=True,
        blank=True,
        verbose_name="Image de couverture",
    )

    # ------------------------------------------------------------------
    # Format et participation
    # ------------------------------------------------------------------
    format = models.CharField(
        max_length=20,
        choices=EventFormat.choices,
        default=EventFormat.IN_PERSON,
        verbose_name="Format",
    )
    participation_type = models.CharField(
        max_length=20,
        choices=ParticipationType.choices,
        default=ParticipationType.FREE,
        verbose_name="Type de participation",
    )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    start_at = models.DateTimeField(
        verbose_name="Date et heure de début",
    )
    end_at = models.DateTimeField(
        verbose_name="Date et heure de fin",
    )

    # ------------------------------------------------------------------
    # Lieu (pour IN_PERSON)
    # ------------------------------------------------------------------
    venue_name = models.CharField(
        max_length=VENUE_NAME_MAX_LENGTH,
        blank=True,
        verbose_name="Nom du lieu",
    )
    address = models.CharField(
        max_length=ADDRESS_MAX_LENGTH,
        blank=True,
        verbose_name="Adresse",
    )
    city = models.CharField(
        max_length=CITY_MAX_LENGTH,
        blank=True,
        db_index=True,
        verbose_name="Ville",
    )
    room = models.CharField(
        max_length=ROOM_MAX_LENGTH,
        blank=True,
        verbose_name="Salle",
    )

    # ------------------------------------------------------------------
    # Accès en ligne (pour ONLINE)
    # ------------------------------------------------------------------
    online_platform = models.CharField(
        max_length=ONLINE_PLATFORM_MAX_LENGTH,
        blank=True,
        verbose_name="Plateforme en ligne",
        help_text="Ex: Zoom, Google Meet, Teams...",
    )
    access_url = models.URLField(
        max_length=ACCESS_URL_MAX_LENGTH,
        blank=True,
        verbose_name="URL d'accès",
        help_text="Lien privé, exposé uniquement aux inscrits et au propriétaire.",
    )

    # ------------------------------------------------------------------
    # Capacité
    # ------------------------------------------------------------------
    capacity_type = models.CharField(
        max_length=20,
        choices=CapacityType.choices,
        default=CapacityType.UNLIMITED,
        verbose_name="Type de capacité",
    )
    capacity_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Limite de places",
        help_text="Obligatoire si capacity_type=LIMITED. NULL si UNLIMITED.",
    )

    # ------------------------------------------------------------------
    # Statut
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.DRAFT,
        db_index=True,
        verbose_name="Statut",
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de publication",
    )

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Date de création",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour",
    )

    # ------------------------------------------------------------------
    # Méta
    # ------------------------------------------------------------------
    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_at"], name="idx_event_status_start"),
            models.Index(fields=["format"], name="idx_event_format"),
            models.Index(fields=["participation_type"], name="idx_event_participation"),
            models.Index(fields=["-start_at"], name="idx_event_start_desc"),
        ]
        constraints = [
            # Contrainte DB : start_at < end_at
            models.CheckConstraint(
                condition=models.Q(start_at__lt=models.F("end_at")),
                name="event_start_before_end",
            ),
            # Contrainte DB : capacity_limit cohérent avec capacity_type
            models.CheckConstraint(
                condition=(
                    models.Q(capacity_type="LIMITED", capacity_limit__gt=0)
                    | models.Q(capacity_type="UNLIMITED", capacity_limit__isnull=True)
                ),
                name="event_capacity_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def is_draft(self) -> bool:
        return self.status == EventStatus.DRAFT

    @property
    def is_published(self) -> bool:
        return self.status == EventStatus.PUBLISHED

    @property
    def is_cancelled(self) -> bool:
        return self.status == EventStatus.CANCELLED

    @property
    def is_completed(self) -> bool:
        return self.status == EventStatus.COMPLETED

    @property
    def is_online(self) -> bool:
        return self.format == EventFormat.ONLINE

    @property
    def is_in_person(self) -> bool:
        return self.format == EventFormat.IN_PERSON

    @property
    def is_free(self) -> bool:
        return self.participation_type == ParticipationType.FREE

    @property
    def is_paid(self) -> bool:
        return self.participation_type == ParticipationType.PAID

    @property
    def has_limited_capacity(self) -> bool:
        return self.capacity_type == CapacityType.LIMITED

    # ------------------------------------------------------------------
    # Méthodes métier
    # ------------------------------------------------------------------
    def calculate_availability(self) -> int | None:
        """
        Calcule le nombre de places restantes.

        Utilise le service de comptage de Registration (dépendance
        unidirectionnelle : Event → Registration, via import local
        pour éviter les cycles).

        Returns:
            - None si la capacité est UNLIMITED
            - Le nombre de places restantes sinon (>= 0)
        """
        if self.capacity_type == CapacityType.UNLIMITED:
            return None

        # Import local pour éviter la dépendance circulaire
        from apps.registrations.selectors import count_active_registrations

        registered_count = count_active_registrations(self)
        return max(0, self.capacity_limit - registered_count)

    def can_transition_to(self, new_status: str) -> bool:
        """
        Vérifie si une transition de statut est autorisée.

        Args:
            new_status: Le statut cible.

        Returns:
            True si la transition est autorisée, False sinon.
        """
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def can_be_edited(self) -> bool:
        """Un événement est modifiable uniquement en DRAFT ou PUBLISHED."""
        return self.status in (EventStatus.DRAFT, EventStatus.PUBLISHED)

    def can_be_deleted(self) -> bool:
        """Un événement ne peut être supprimé qu'en DRAFT."""
        return self.status == EventStatus.DRAFT