"""
Constantes et enums du module Certificates.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# ENUM : Statut du certificat
# ==================================================================
class CertificateStatus(models.TextChoices):
    """
    Statut d'un certificat.

    - PENDING : certificat créé, PDF en cours de génération.
    - ISSUED  : certificat officiellement émis, PDF prêt.
    - REVOKED : certificat invalidé (fraude, erreur, etc.).
    """
    PENDING = "PENDING", _("En attente")
    ISSUED = "ISSUED", _("Émis")
    REVOKED = "REVOKED", _("Révoqué")


# ==================================================================
# TRANSITIONS AUTORISÉES
# ==================================================================
ALLOWED_STATUS_TRANSITIONS = {
    CertificateStatus.PENDING: [
        CertificateStatus.ISSUED,
        CertificateStatus.REVOKED,
    ],
    CertificateStatus.ISSUED: [
        CertificateStatus.REVOKED,
    ],
    CertificateStatus.REVOKED: [],  # terminal
}


# ==================================================================
# RÉFÉRENCE
# ==================================================================
REFERENCE_PREFIX = "CERT"
REFERENCE_SUFFIX_LENGTH = 6
REFERENCE_MAX_LENGTH = 30
REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O/1/I/L


# ==================================================================
# VERIFICATION CODE
# ==================================================================
VERIFICATION_CODE_BYTES = 8  # 8 bytes = 16 caractères hex
VERIFICATION_CODE_MAX_LENGTH = 64


# ==================================================================
# STATUTS ACTIFS (utilisés pour l'éligibilité)
# ==================================================================
# Un certificat actif empêche la génération d'un nouveau.
ACTIVE_STATUSES = (
    CertificateStatus.PENDING,
    CertificateStatus.ISSUED,
)