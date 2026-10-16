"""
Constantes et enums du module Registration.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# ENUM : Statut de l'inscription
# ==================================================================
class RegistrationStatus(models.TextChoices):
    """
    Statut d'une inscription.

    - PENDING   : inscription enregistrée, en attente de confirmation
                  (utilisé principalement pour les événements payants
                  en attente de paiement).
    - CONFIRMED : inscription validée, le participant est attendu.
    - CANCELLED : inscription annulée (par le participant, l'organisateur
                  ou le système). État terminal.
    """
    PENDING = "PENDING", _("En attente")
    CONFIRMED = "CONFIRMED", _("Confirmée")
    CANCELLED = "CANCELLED", _("Annulée")


# ==================================================================
# TRANSITIONS AUTORISÉES
# ==================================================================
ALLOWED_STATUS_TRANSITIONS = {
    RegistrationStatus.PENDING: [
        RegistrationStatus.CONFIRMED,
        RegistrationStatus.CANCELLED,
    ],
    RegistrationStatus.CONFIRMED: [
        RegistrationStatus.CANCELLED,
    ],
    RegistrationStatus.CANCELLED: [],  # terminal
}


# ==================================================================
# STATUTS ACTIFS (utilisés pour la capacité et la double inscription)
# ==================================================================
# Une inscription active occupe une place.
ACTIVE_STATUSES = (
    RegistrationStatus.PENDING,
    RegistrationStatus.CONFIRMED,
)


# ==================================================================
# RÉFÉRENCE
# ==================================================================
REFERENCE_PREFIX = "EVF-REG"
REFERENCE_SUFFIX_LENGTH = 6
REFERENCE_MAX_LENGTH = 50
REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O/1/I/L