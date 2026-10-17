"""
Génération du QR code pour un certificat.

Le QR code pointe vers l'URL publique de vérification :
    {CERTIFICATE_VERIFY_URL_BASE}/{verification_code}

Il ne contient AUCUNE donnée privée (pas de nom, pas d'email).
"""

import io
import logging

import qrcode
from django.conf import settings
from qrcode.constants import ERROR_CORRECT_M

logger = logging.getLogger(__name__)


def build_verify_url(verification_code: str) -> str:
    """Construit l'URL publique de vérification."""
    base = settings.CERTIFICATE_VERIFY_URL_BASE.rstrip("/")
    return f"{base}/{verification_code}"


def generate_qr_image_bytes(verification_code: str) -> bytes:
    """
    Génère une image QR code (PNG) pointant vers l'URL de vérification.

    Args:
        verification_code: Le code unique du certificat.

    Returns:
        Les bytes de l'image PNG.
    """
    url = build_verify_url(verification_code)

    qr = qrcode.QRCode(
        version=None,           # Taille auto
        error_correction=ERROR_CORRECT_M,  # ~15% de correction d'erreur
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.read()