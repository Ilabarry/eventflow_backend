"""
Services métier du module Event.

Les services encapsulent la logique métier complexe :
    - Création d'un événement
    - Modification
    - Publication (avec validation complète)
    - Annulation
    - Suppression
    - Calcul de disponibilité

Avantages :
    - La logique n'est PAS dans les vues ni les serializers
    - Testable unitairement
    - Réutilisable (vues, admin, tâches cron, scripts)
    - Transactionnel quand nécessaire (@transaction.atomic)
"""

import logging
from django.db import transaction


from django.db import transaction
from django.utils import timezone

from apps.events.constants import EventFormat, EventStatus
from apps.events.models import Category, Event
from apps.events.validators import (
    validate_capacity,
    validate_dates,
    validate_format_data,
)
from common.exceptions.business import (
    CategoryInUse,
    EventAlreadyCancelled,
    EventAlreadyPublished,
    EventCannotBeDeleted,
    EventCannotBeEdited,
    EventCannotBePublished,
    InvalidEventStatusTransition,
)

logger = logging.getLogger(__name__)


# ==================================================================
# SERVICE : Event
# ==================================================================
class EventService:
    """
    Service métier pour les événements.

    Toutes les opérations importantes passent par ici.
    """

    # ------------------------------------------------------------------
    # CRÉATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create_event(*, organizer, validated_data: dict) -> Event:
        """
        Crée un nouvel événement en statut DRAFT.

        Args:
            organizer: L'utilisateur propriétaire (request.user).
            validated_data: Données validées par EventCreateSerializer.

        Returns:
            L'instance Event créée.
        """
        event = Event.objects.create(
            organizer=organizer,
            status=EventStatus.DRAFT,
            **validated_data,
        )

        logger.info(
            "Event created | id=%s | organizer=%s | title=%s",
            event.id, organizer.email, event.title,
        )

        return event

    # ------------------------------------------------------------------
    # MODIFICATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def update_event(*, event: Event, validated_data: dict) -> Event:
        """
        Met à jour un événement.

        Vérifie que l'événement est modifiable (DRAFT ou PUBLISHED).
        Si l'événement est PUBLISHED, on revalide les règles de publication
        pour éviter de casser un événement publié.

        Raises:
            EventCannotBeEdited: Si l'événement n'est plus modifiable.
        """
        if not event.can_be_edited():
            raise EventCannotBeEdited(
                detail=f"Un événement en statut '{event.status}' ne peut plus être modifié."
            )

        for field, value in validated_data.items():
            setattr(event, field, value)

        event.save()

        logger.info(
            "Event updated | id=%s | organizer=%s",
            event.id, event.organizer.email,
        )

        return event

    # ------------------------------------------------------------------
    # PUBLICATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def publish_event(*, event: Event) -> Event:
        """
        Publie un événement.

        Vérifie :
            - Statut actuel autorisé (DRAFT ou PUBLISHED → non)
            - Données complètes (titre, dates, format, lieu/lien...)

        Effet :
            - status = PUBLISHED
            - published_at = now()

        Raises:
            EventAlreadyPublished: Si déjà publié.
            InvalidEventStatusTransition: Si transition interdite.
            EventCannotBePublished: Si données incomplètes.
        """
        # 1. Vérifier la transition
        if event.status == EventStatus.PUBLISHED:
            raise EventAlreadyPublished()

        if not event.can_transition_to(EventStatus.PUBLISHED):
            raise InvalidEventStatusTransition(
                detail=f"Transition '{event.status}' → 'PUBLISHED' non autorisée."
            )

        # 2. Valider les données de publication
        EventService._validate_for_publication(event)

        # 3. Effectuer la transition
        event.status = EventStatus.PUBLISHED
        event.published_at = timezone.now()
        event.save(update_fields=["status", "published_at", "updated_at"])

        logger.info(
            "Event published | id=%s | organizer=%s",
            event.id, event.organizer.email,
        )

        # ⚠️ NOUVEAU : notifier tous les participants confirmés
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                from apps.registrations.constants import RegistrationStatus
                from apps.registrations.models import Registration
                from apps.accounts.models import User

                participant_ids = Registration.objects.filter(
                    event=event,
                    status=RegistrationStatus.CONFIRMED,
                ).values_list("participant_id", flat=True).distinct()

                if participant_ids:
                    users = User.objects.filter(id__in=participant_ids)
                    NotificationService.notify_queryset(
                        queryset=users,
                        title="Nouvel événement publié",
                        message=f"« {event.title} » est maintenant disponible.",
                        notification_type=NotificationType.EVENT_PUBLICATION,
                        related_entity_type="event",
                        related_entity_id=str(event.id),
                        metadata={"url": f"/events/{event.id}"},
                    )
        except Exception as e:
            logger.warning("Notification failed on event publish | err=%s", e)

        return event

    # ------------------------------------------------------------------
    # ANNULATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def cancel_event(*, event: Event) -> Event:
        """
        Annule un événement.

        Raises:
            EventAlreadyCancelled: Si déjà annulé.
            InvalidEventStatusTransition: Si transition interdite.
        """
        if event.status == EventStatus.CANCELLED:
            raise EventAlreadyCancelled()

        if not event.can_transition_to(EventStatus.CANCELLED):
            raise InvalidEventStatusTransition(
                detail=f"Transition '{event.status}' → 'CANCELLED' non autorisée."
            )

        event.status = EventStatus.CANCELLED
        event.save(update_fields=["status", "updated_at"])

        logger.info(
            "Event cancelled | id=%s | organizer=%s",
            event.id, event.organizer.email,
        )

        # ⚠️ NOUVEAU : notifier tous les participants confirmés
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                from apps.registrations.constants import RegistrationStatus
                from apps.registrations.models import Registration
                from apps.accounts.models import User

                participant_ids = Registration.objects.filter(
                    event=event,
                    status=RegistrationStatus.CONFIRMED,
                ).values_list("participant_id", flat=True).distinct()

                if participant_ids:
                    users = User.objects.filter(id__in=participant_ids)
                    NotificationService.notify_queryset(
                        queryset=users,
                        title="Événement annulé",
                        message=f"« {event.title} » a été annulé.",
                        notification_type=NotificationType.EVENT_UPDATE,
                        related_entity_type="event",
                        related_entity_id=str(event.id),
                        metadata={"url": f"/events/{event.id}"},
                    )
        except Exception as e:
            logger.warning("Notification failed on event cancel | err=%s", e)

        return event

    # ------------------------------------------------------------------
    # SUPPRESSION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def delete_event(*, event: Event) -> None:
        """
        Supprime un événement.

        Seuls les brouillons peuvent être supprimés. Un événement
        publié doit d'abord être annulé.

        Raises:
            EventCannotBeDeleted: Si l'événement n'est pas en DRAFT.
        """
        if not event.can_be_deleted():
            raise EventCannotBeDeleted(
                detail=f"Impossible de supprimer un événement en statut '{event.status}'."
            )

        event_id = event.id
        event.delete()

        logger.info("Event deleted | id=%s", event_id)

    # ------------------------------------------------------------------
    # VALIDATION INTERNE (avant publication)
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_for_publication(event: Event) -> None:
        """
        Vérifie que toutes les données obligatoires sont présentes
        avant de publier un événement.

        Raises:
            EventCannotBePublished: Si une règle est violée.
        """
        errors = {}

        # Champs obligatoires
        if not event.title:
            errors["title"] = "Le titre est obligatoire."

        if not event.short_description:
            errors["short_description"] = "La description courte est obligatoire."

        if not event.description:
            errors["description"] = "La description complète est obligatoire."

        if not event.category_id:
            errors["category"] = "La catégorie est obligatoire."

        # Dates
        try:
            validate_dates(event.start_at, event.end_at)
        except Exception as e:
            errors["dates"] = str(e)

        # Capacité
        try:
            validate_capacity(event.capacity_type, event.capacity_limit)
        except Exception as e:
            errors["capacity"] = str(e)

        # Format (lieu ou lien)
        try:
            validate_format_data(
                event_format=event.format,
                venue_name=event.venue_name,
                address=event.address,
                city=event.city,
                access_url=event.access_url,
            )
        except Exception as e:
            errors["format"] = str(e)

        if errors:
            raise EventCannotBePublished(
                detail={"message": "Données incomplètes pour la publication.", "errors": errors}
            )


# ==================================================================
# SERVICE : Category
# ==================================================================
class CategoryService:
    """Service métier pour les catégories."""

    @staticmethod
    @transaction.atomic
    def create_category(*, validated_data: dict) -> Category:
        """Crée une catégorie."""
        category = Category.objects.create(**validated_data)
        logger.info("Category created | id=%s | name=%s", category.id, category.name)
        return category

    @staticmethod
    @transaction.atomic
    def update_category(*, category: Category, validated_data: dict) -> Category:
        """Met à jour une catégorie."""
        for field, value in validated_data.items():
            setattr(category, field, value)
        category.save()
        logger.info("Category updated | id=%s", category.id)
        return category

    @staticmethod
    @transaction.atomic
    def delete_category(*, category: Category) -> None:
        """
        Supprime une catégorie si elle n'est pas utilisée.

        Raises:
            CategoryInUse: Si au moins un événement utilise cette catégorie.
        """
        if category.events.exists():
            raise CategoryInUse(
                detail=f"Impossible de supprimer la catégorie '{category.name}' "
                       f"car elle est utilisée par {category.events.count()} événement(s)."
            )
        category_id = category.id
        category.delete()
        logger.info("Category deleted | id=%s", category_id)