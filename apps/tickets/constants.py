"""
Constantes et enums du module Tickets.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# ENUM : Statut d'un ticket
# ==================================================================
class TicketStatus(models.TextChoices):
    """
    Statut d'un ticket individuel.

    - VALID     : ticket émis, prêt à être utilisé.
    - USED      : ticket scanné à l'entrée (check-in effectué).
    - EXPIRED   : événement terminé sans check-in.
    - CANCELLED : ticket annulé (inscription annulée, remboursement, etc.).
    """
    VALID = "VALID", _("Valide")
    USED = "USED", _("Utilisé")
    EXPIRED = "EXPIRED", _("Expiré")
    CANCELLED = "CANCELLED", _("Annulé")


# ==================================================================
# TRANSITIONS AUTORISÉES
# ==================================================================
ALLOWED_STATUS_TRANSITIONS = {
    TicketStatus.VALID: [
        TicketStatus.USED,
        TicketStatus.EXPIRED,
        TicketStatus.CANCELLED,
    ],
    TicketStatus.USED: [],       # terminal
    TicketStatus.EXPIRED: [],    # terminal
    TicketStatus.CANCELLED: [],  # terminal
}


# ==================================================================
# RÉFÉRENCE
# ==================================================================
REFERENCE_PREFIX = "EVF-TKT"
REFERENCE_SUFFIX_LENGTH = 8
REFERENCE_MAX_LENGTH = 50
REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


# ==================================================================
# CONFIGURATION
# ==================================================================
DEFAULT_CURRENCY = "XOF"
CURRENCY_CODE_LENGTH = 3
PRICE_MAX_DIGITS = 12
PRICE_DECIMAL_PLACES = 2

# Nombre maximal de tickets par inscription (V1)
TICKETS_PER_REGISTRATION = 1