"""
Exceptions métier transversales.

Ces exceptions sont utilisées par les services pour signaler
des erreurs métier. DRF les convertit automatiquement en réponse
HTTP grâce au handler personnalisé (common/exceptions/handlers.py).

Chaque exception porte :
    - un message lisible
    - un code HTTP associé
    - éventuellement des détails (dictionnaire)
"""

from rest_framework import status
from rest_framework.exceptions import APIException


# ==================================================================
# BASE
# ==================================================================
class BusinessException(APIException):
    """
    Exception métier générique.

    Toutes les exceptions métier d'EVENTFLOW héritent de cette classe.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Une erreur métier est survenue."
    default_code = "business_error"


# ==================================================================
# EVENT — Exceptions spécifiques
# ==================================================================
class EventCannotBePublished(BusinessException):
    """
    Levée lorsqu'un événement ne remplit pas les conditions de publication.

    Exemples :
        - Titre manquant
        - Dates incohérentes
        - Lieu manquant pour un événement présentiel
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cet événement ne peut pas être publié."
    default_code = "event_cannot_be_published"


class EventAlreadyPublished(BusinessException):
    """Levée lorsqu'on essaie de publier un événement déjà publié."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cet événement est déjà publié."
    default_code = "event_already_published"


class EventAlreadyCancelled(BusinessException):
    """Levée lorsqu'on essaie d'annuler un événement déjà annulé."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cet événement est déjà annulé."
    default_code = "event_already_cancelled"


class EventCannotBeEdited(BusinessException):
    """Levée lorsqu'on essaie de modifier un événement non modifiable."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cet événement ne peut plus être modifié."
    default_code = "event_cannot_be_edited"


class EventCannotBeDeleted(BusinessException):
    """Levée lorsqu'on essaie de supprimer un événement non supprimable."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Seuls les brouillons peuvent être supprimés."
    default_code = "event_cannot_be_deleted"


class InvalidEventStatusTransition(BusinessException):
    """Levée lorsqu'une transition de statut est interdite."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Transition de statut invalide."
    default_code = "invalid_status_transition"


class EventCapacityInvalid(BusinessException):
    """Levée lorsque la capacité est incohérente."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "La configuration de la capacité est invalide."
    default_code = "event_capacity_invalid"


class OnlineEventDataInvalid(BusinessException):
    """Levée lorsque les données d'un événement en ligne sont incomplètes."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Les données de l'événement en ligne sont incomplètes."
    default_code = "online_event_data_invalid"


class InPersonEventDataInvalid(BusinessException):
    """Levée lorsque les données d'un événement présentiel sont incomplètes."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Les données de l'événement en présentiel sont incomplètes."
    default_code = "in_person_event_data_invalid"


class UnauthorizedEventAccess(BusinessException):
    """Levée lorsqu'un utilisateur tente d'accéder à un événement sans droits."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Vous n'êtes pas autorisé à effectuer cette action sur cet événement."
    default_code = "unauthorized_event_access"


# ==================================================================
# CATEGORY — Exceptions spécifiques
# ==================================================================
class CategoryInUse(BusinessException):
    """Levée lorsqu'on essaie de supprimer une catégorie utilisée."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cette catégorie est utilisée par au moins un événement."
    default_code = "category_in_use"


class CategoryAlreadyExists(BusinessException):
    """Levée lorsqu'on essaie de créer une catégorie avec un nom existant."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Une catégorie avec ce nom existe déjà."
    default_code = "category_already_exists"