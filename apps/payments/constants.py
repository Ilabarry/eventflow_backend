"""
Constantes et enums du module Payment.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# ENUM : Statut du paiement
# ==================================================================
class PaymentStatus(models.TextChoices):
    """
    Statut d'un paiement.

    - PENDING   : paiement initié, en attente de confirmation.
    - SUCCESS   : paiement confirmé, fonds reçus.
    - FAILED    : paiement échoué (fonds insuffisants, refus...).
    - CANCELLED : paiement annulé par l'utilisateur.
    - REFUNDED  : paiement remboursé (après SUCCESS).

    Note : on n'a PAS ajouté PROCESSING et EXPIRED pour le MVP.
    Ils seront ajoutés en V2 pour les providers asynchrones.
    """
    PENDING = "PENDING", _("En attente")
    SUCCESS = "SUCCESS", _("Réussi")
    FAILED = "FAILED", _("Échoué")
    CANCELLED = "CANCELLED", _("Annulé")
    REFUNDED = "REFUNDED", _("Remboursé")


# ==================================================================
# ENUM : Méthode de paiement
# ==================================================================
class PaymentMethod(models.TextChoices):
    """
    Catégorie large de paiement (indépendante du provider).

    - MOBILE_MONEY : Orange Money, Wave, Yas...
    - CARD         : cartes bancaires (Visa, Mastercard...)
    - DEVELOPMENT  : provider de développement (tests)
    """
    MOBILE_MONEY = "MOBILE_MONEY", _("Mobile Money")
    CARD = "CARD", _("Carte bancaire")
    DEVELOPMENT = "DEVELOPMENT", _("Développement (test)")


# ==================================================================
# ENUM : Provider de paiement
# ==================================================================
class PaymentProvider(models.TextChoices):
    """
    Prestataire technique de paiement.

    ⚠️ Seul DEVELOPMENT est fonctionnel pour l'instant.
    Les autres sont des placeholders (V2).
    """
    DEVELOPMENT = "DEVELOPMENT", _("Développement")
    ORANGE_MONEY = "ORANGE_MONEY", _("Orange Money")
    WAVE = "WAVE", _("Wave")
    YAS = "YAS", _("Yas")
    CARD = "CARD", _("Carte bancaire")


# ==================================================================
# TRANSITIONS AUTORISÉES
# ==================================================================
ALLOWED_STATUS_TRANSITIONS = {
    PaymentStatus.PENDING: [
        PaymentStatus.SUCCESS,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    ],
    PaymentStatus.SUCCESS: [
        PaymentStatus.REFUNDED,
    ],
    PaymentStatus.FAILED: [],      # terminal
    PaymentStatus.CANCELLED: [],   # terminal
    PaymentStatus.REFUNDED: [],    # terminal
}


# ==================================================================
# STATUTS ACTIFS (utilisés pour l'idempotence)
# ==================================================================
# Un paiement actif empêche un nouveau paiement d'être initié.
ACTIVE_STATUSES = (
    PaymentStatus.PENDING,
    PaymentStatus.SUCCESS,
)


# ==================================================================
# RÉFÉRENCE INTERNE
# ==================================================================
REFERENCE_PREFIX = "EVF-PAY"
REFERENCE_SUFFIX_LENGTH = 6
REFERENCE_MAX_LENGTH = 50
REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O/1/I/L


# ==================================================================
# CONFIGURATION
# ==================================================================
DEFAULT_CURRENCY = "XOF"
CURRENCY_CODE_LENGTH = 3
AMOUNT_MAX_DIGITS = 12
AMOUNT_DECIMAL_PLACES = 2