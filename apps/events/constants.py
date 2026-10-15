"""
Constantes et enums du module Event.

On utilise models.TextChoices (Django) plutôt qu'enum.Enum car :
    - Intégration native avec Django ORM et les migrations
    - Compatibilité avec les serializers (ChoiceField)
    - Libellés traduits dans l'admin
    - Les valeurs sont des chaînes (facilement sérialisables en JSON)
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# ENUMS : Format de l'événement
# ==================================================================
class EventFormat(models.TextChoices):
    """
    Format de l'événement : en ligne ou présentiel.
    
    Note : on n'a pas prévu HYBRID pour l'instant. Si le besoin
    apparaît, il suffira d'ajouter une valeur.
    """
    ONLINE = "ONLINE", _("En ligne")
    IN_PERSON = "IN_PERSON", _("Présentiel")


# ==================================================================
# ENUMS : Type de participation
# ==================================================================
class ParticipationType(models.TextChoices):
    """
    Type de participation : gratuit ou payant.
    
    IMPORTANT : Event ne stocke PAS le prix. Il indique seulement
    si la participation est gratuite ou payante. Les prix et types
    de tickets seront gérés dans le module tickets.
    """
    FREE = "FREE", _("Gratuit")
    PAID = "PAID", _("Payant")


# ==================================================================
# ENUMS : Type de capacité
# ==================================================================
class CapacityType(models.TextChoices):
    """
    Type de capacité : limitée ou illimitée.
    
    Si LIMITED : capacity_limit est obligatoire (> 0).
    Si UNLIMITED : capacity_limit doit être NULL.
    """
    LIMITED = "LIMITED", _("Places limitées")
    UNLIMITED = "UNLIMITED", _("Places illimitées")


# ==================================================================
# ENUMS : Statut de l'événement
# ==================================================================
class EventStatus(models.TextChoices):
    """
    Statut de l'événement.
    
    Transitions autorisées :
        DRAFT     → PUBLISHED, CANCELLED
        PUBLISHED → COMPLETED, CANCELLED
        COMPLETED → (terminal)
        CANCELLED → (terminal)
    """
    DRAFT = "DRAFT", _("Brouillon")
    PUBLISHED = "PUBLISHED", _("Publié")
    COMPLETED = "COMPLETED", _("Terminé")
    CANCELLED = "CANCELLED", _("Annulé")


# ==================================================================
# TRANSITIONS AUTORISÉES
# ==================================================================
# Dictionnaire {statut actuel: [statuts cibles autorisés]}
ALLOWED_STATUS_TRANSITIONS = {
    EventStatus.DRAFT: [EventStatus.PUBLISHED, EventStatus.CANCELLED],
    EventStatus.PUBLISHED: [EventStatus.COMPLETED, EventStatus.CANCELLED],
    EventStatus.COMPLETED: [],
    EventStatus.CANCELLED: [],
}


# ==================================================================
# CONSTANTES DE VALIDATION
# ==================================================================
# Taille maximale d'une image de couverture (5 Mo)
MAX_COVER_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo en octets

# Formats d'image autorisés
ALLOWED_COVER_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
ALLOWED_COVER_IMAGE_MIMETYPES = (
    "image/jpeg",
    "image/png",
    "image/webp",
)

# Longueurs maximales
TITLE_MAX_LENGTH = 200
SHORT_DESCRIPTION_MAX_LENGTH = 300
CITY_MAX_LENGTH = 100
VENUE_NAME_MAX_LENGTH = 200
ADDRESS_MAX_LENGTH = 255
ROOM_MAX_LENGTH = 100
ONLINE_PLATFORM_MAX_LENGTH = 100
ACCESS_URL_MAX_LENGTH = 500


# ==================================================================
# CHAMPS DE TRI AUTORISÉS (liste blanche)
# ==================================================================
# On n'autorise QUE ces champs dans ?ordering=...
# Sinon un utilisateur pourrait injecter du SQL via order_by.
ALLOWED_ORDERING_FIELDS = (
    "start_at",
    "-start_at",
    "created_at",
    "-created_at",
    "published_at",
    "-published_at",
    "title",
    "-title",
)


# ==================================================================
# CHAMPS DE RECHERCHE
# ==================================================================
# Champs sur lesquels porte la recherche ?search=...
SEARCH_FIELDS = ("title", "short_description", "description", "city")