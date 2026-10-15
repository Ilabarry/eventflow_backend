"""
Validateurs métier du module Event.

Ces validateurs sont appelés :
    - par les serializers (validation API)
    - par les services (validation avant publication)
    - par les modèles si nécessaire

Ils lèvent ValidationError (Django) que DRF convertit
automatiquement en réponse 400.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.events.constants import (
    ALLOWED_COVER_IMAGE_EXTENSIONS,
    ALLOWED_COVER_IMAGE_MIMETYPES,
    MAX_COVER_IMAGE_SIZE,
    CapacityType,
    EventFormat,
)


# ==================================================================
# VALIDATION : Dates
# ==================================================================
def validate_dates(start_at, end_at) -> None:
    """
    Vérifie la cohérence des dates d'un événement.

    Règles :
        - start_at < end_at
        - start_at doit être dans le futur (à la création/publication)
        - La durée maximale ne doit pas dépasser 30 jours

    Args:
        start_at: Date de début (datetime).
        end_at: Date de fin (datetime).

    Raises:
        ValidationError: Si une règle est violée.
    """
    if not start_at or not end_at:
        raise ValidationError(
            _("Les dates de début et de fin sont obligatoires.")
        )

    if start_at >= end_at:
        raise ValidationError(
            _("La date de début doit être antérieure à la date de fin.")
        )

    # La date de début doit être dans le futur
    if start_at < timezone.now():
        raise ValidationError(
            _("La date de début doit être dans le futur.")
        )

    # Durée maximale : 30 jours
    max_duration = timezone.timedelta(days=30)
    if (end_at - start_at) > max_duration:
        raise ValidationError(
            _("Un événement ne peut pas durer plus de 30 jours.")
        )


# ==================================================================
# VALIDATION : Capacité
# ==================================================================
def validate_capacity(capacity_type: str, capacity_limit) -> None:
    """
    Vérifie la cohérence entre capacity_type et capacity_limit.

    Règles :
        - Si LIMITED : capacity_limit obligatoire et > 0
        - Si UNLIMITED : capacity_limit doit être NULL

    Args:
        capacity_type: 'LIMITED' ou 'UNLIMITED'.
        capacity_limit: Nombre entier ou None.

    Raises:
        ValidationError: Si une règle est violée.
    """
    if capacity_type == CapacityType.LIMITED:
        if capacity_limit is None:
            raise ValidationError(
                _("La limite de places est obligatoire pour un événement à capacité limitée.")
            )
        if capacity_limit <= 0:
            raise ValidationError(
                _("La limite de places doit être supérieure à 0.")
            )
        if capacity_limit > 1_000_000:
            raise ValidationError(
                _("La limite de places ne peut pas dépasser 1 000 000.")
            )

    elif capacity_type == CapacityType.UNLIMITED:
        if capacity_limit is not None:
            raise ValidationError(
                _("La limite de places doit être vide pour un événement à capacité illimitée.")
            )


# ==================================================================
# VALIDATION : Données selon le format
# ==================================================================
def validate_format_data(
    event_format: str,
    venue_name: str = "",
    address: str = "",
    city: str = "",
    access_url: str = "",
) -> None:
    """
    Vérifie que les données correspondent au format déclaré.

    Règles :
        - Si IN_PERSON : venue_name, address, city obligatoires
        - Si ONLINE : access_url obligatoire (lien valide)

    Args:
        event_format: 'IN_PERSON' ou 'ONLINE'.
        venue_name, address, city: Champs présentiel.
        access_url: URL d'accès en ligne.

    Raises:
        ValidationError: Si les données sont incomplètes.
    """
    if event_format == EventFormat.IN_PERSON:
        missing = []
        if not venue_name:
            missing.append("venue_name")
        if not address:
            missing.append("address")
        if not city:
            missing.append("city")

        if missing:
            raise ValidationError(
                _("Événement en présentiel : les champs suivants sont obligatoires : %(fields)s."),
                params={"fields": ", ".join(missing)},
            )

    elif event_format == EventFormat.ONLINE:
        if not access_url:
            raise ValidationError(
                _("Événement en ligne : l'URL d'accès est obligatoire pour la publication.")
            )


# ==================================================================
# VALIDATION : Image de couverture
# ==================================================================
def validate_cover_image(image) -> None:
    """
    Vérifie le type, la taille et l'extension de l'image.

    Règles :
        - Taille max : 5 Mo
        - Formats : JPEG, PNG, WebP
        - Extension autorisée
        - Content-Type autorisé

    Args:
        image: Fichier image uploadé (InMemoryUploadedFile ou TemporaryUploadedFile).

    Raises:
        ValidationError: Si une règle est violée.
    """
    if image is None:
        return

    # Taille
    if image.size > MAX_COVER_IMAGE_SIZE:
        raise ValidationError(
            _("L'image ne doit pas dépasser %(max)s Mo."),
            params={"max": MAX_COVER_IMAGE_SIZE // (1024 * 1024)},
        )

    # Extension
    name = image.name.lower()
    if not name.endswith(ALLOWED_COVER_IMAGE_EXTENSIONS):
        raise ValidationError(
            _("Extension d'image non autorisée. Formats acceptés : %(formats)s."),
            params={"formats": ", ".join(ALLOWED_COVER_IMAGE_EXTENSIONS)},
        )

    # Content-Type (si disponible)
    content_type = getattr(image, "content_type", None)
    if content_type and content_type not in ALLOWED_COVER_IMAGE_MIMETYPES:
        raise ValidationError(
            _("Type MIME non autorisé : %(mime)s."),
            params={"mime": content_type},
        )