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

# ==================================================================
# REGISTRATION — Exceptions spécifiques
# ==================================================================
class AlreadyRegistered(BusinessException):
    """Levée lorsqu'un participant tente une double inscription active."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Vous êtes déjà inscrit à cet événement."
    default_code = "already_registered"


class EventFull(BusinessException):
    """Levée lorsque la capacité maximale de l'événement est atteinte."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cet événement est complet."
    default_code = "event_full"


class EventNotPublished(BusinessException):
    """Levée lorsqu'on tente de s'inscrire à un événement non publié."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cet événement n'accepte pas encore d'inscriptions."
    default_code = "event_not_published"


class EventCancelled(BusinessException):
    """Levée lorsqu'on tente de s'inscrire à un événement annulé."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cet événement est annulé."
    default_code = "event_cancelled"


class EventCompleted(BusinessException):
    """Levée lorsqu'on tente de s'inscrire à un événement terminé."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cet événement est terminé."
    default_code = "event_completed"


class RegistrationAlreadyCancelled(BusinessException):
    """Levée lorsqu'on annule une inscription déjà annulée."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cette inscription est déjà annulée."
    default_code = "registration_already_cancelled"


class RegistrationNotAllowed(BusinessException):
    """Levée lorsqu'un utilisateur tente une action non autorisée."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Vous n'êtes pas autorisé à effectuer cette action."
    default_code = "registration_not_allowed"


class PaymentRequired(BusinessException):
    """Levée lorsqu'un événement payant est sélectionné sans TicketType."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cet événement est payant. Un type de ticket est requis."
    default_code = "payment_required"


    # ==================================================================
# PAYMENT — Exceptions spécifiques
# ==================================================================
class PaymentAlreadySuccessful(BusinessException):
    """Levée lorsqu'un paiement SUCCESS existe déjà pour une inscription."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Un paiement réussi existe déjà pour cette inscription."
    default_code = "payment_already_successful"


class PaymentNotFound(BusinessException):
    """Levée lorsque le paiement est introuvable."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Paiement introuvable."
    default_code = "payment_not_found"


class PaymentNotPayable(BusinessException):
    """Levée lorsque l'inscription n'est pas payable (déjà confirmée, etc.)."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cette inscription n'est pas payable."
    default_code = "payment_not_payable"


class PaymentAlreadyCancelled(BusinessException):
    """Levée lorsqu'on annule un paiement déjà annulé."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce paiement est déjà annulé."
    default_code = "payment_already_cancelled"


class PaymentAlreadyRefunded(BusinessException):
    """Levée lorsqu'on rembourse un paiement déjà remboursé."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce paiement est déjà remboursé."
    default_code = "payment_already_refunded"


class InvalidPaymentState(BusinessException):
    """Levée lorsque l'état du paiement ne permet pas l'action demandée."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "L'état du paiement ne permet pas cette action."
    default_code = "invalid_payment_state"


class PaymentProviderUnavailable(BusinessException):
    """Levée lorsque le provider de paiement est indisponible."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Le service de paiement est temporairement indisponible."
    default_code = "payment_provider_unavailable"


class PaymentProviderError(BusinessException):
    """Levée lorsqu'une erreur survient côté provider."""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Erreur du service de paiement."
    default_code = "payment_provider_error"


class PaymentOwnershipError(BusinessException):
    """Levée lorsqu'un utilisateur tente d'accéder à un paiement qui n'est pas le sien."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Vous n'êtes pas autorisé à accéder à ce paiement."
    default_code = "payment_ownership_error"

# ==================================================================
# ATTENDANCE — Exceptions spécifiques
# ==================================================================
class AttendanceRegistrationNotFound(BusinessException):
    """Levée lorsque l'inscription visée par un check-in n'existe pas."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Inscription introuvable."
    default_code = "attendance_registration_not_found"


class RegistrationNotEligibleForCheckIn(BusinessException):
    """
    Levée lorsque l'inscription ne permet pas d'enregistrer une présence.

    Exemples : inscription annulée, inscription en attente de paiement.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cette inscription ne permet pas d'enregistrer une présence."
    default_code = "registration_not_eligible_for_check_in"


class CheckInNotOpen(BusinessException):
    """Levée lorsqu'on tente un check-in en dehors de la fenêtre autorisée."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Le check-in n'est pas ouvert pour cet événement."
    default_code = "check_in_not_open"


class AlreadyCheckedIn(BusinessException):
    """Levée lorsque le participant est déjà enregistré comme présent."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce participant est déjà enregistré comme présent."
    default_code = "already_checked_in"