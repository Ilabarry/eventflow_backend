"""
Génération du PDF de certificat avec ReportLab.

Architecture :
    - Une fonction principale : generate_certificate_pdf(certificate) -> bytes
    - Un template simple mais professionnel (titre, nom, event, QR)

Décision : ReportLab (pas WeasyPrint) car installation sans friction
sur Windows et performances excellentes pour 1 page.
"""

import io
import logging

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.certificates.qr import generate_qr_image_bytes

logger = logging.getLogger(__name__)


# ==================================================================
# COULEURS ET MISE EN PAGE
# ==================================================================
COLOR_PRIMARY = HexColor("#1e3a8a")     # Bleu foncé
COLOR_ACCENT = HexColor("#3b82f6")      # Bleu clair
COLOR_TEXT = HexColor("#1f2937")        # Gris foncé
COLOR_MUTED = HexColor("#6b7280")       # Gris moyen

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # Paysage (plus joli pour un certificat)


# ==================================================================
# GÉNÉRATION
# ==================================================================
def generate_certificate_pdf(certificate) -> bytes:
    """
    Génère le PDF d'un certificat.

    Args:
        certificate: instance Certificate (avec relations chargées).

    Returns:
        Les bytes du PDF.
    """
    registration = certificate.registration
    participant = registration.participant
    event = registration.event

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    # --- Fond blanc + bordure décorative ---
    c.setStrokeColor(COLOR_PRIMARY)
    c.setLineWidth(4)
    c.rect(1 * cm, 1 * cm, PAGE_WIDTH - 2 * cm, PAGE_HEIGHT - 2 * cm)

    c.setStrokeColor(COLOR_ACCENT)
    c.setLineWidth(1)
    c.rect(1.3 * cm, 1.3 * cm, PAGE_WIDTH - 2.6 * cm, PAGE_HEIGHT - 2.6 * cm)

    # --- Header : EVENTFLOW ---
    c.setFillColor(COLOR_PRIMARY)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 3 * cm, "EVENTFLOW")

    # --- Titre ---
    c.setFillColor(COLOR_TEXT)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 5 * cm, "CERTIFICAT")

    c.setFont("Helvetica", 16)
    c.setFillColor(COLOR_MUTED)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 6 * cm, "de participation")

    # --- Participant ---
    c.setFillColor(COLOR_TEXT)
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 9 * cm, "Décerné à")

    c.setFillColor(COLOR_PRIMARY)
    c.setFont("Helvetica-Bold", 28)
    full_name = f"{participant.first_name} {participant.last_name}".strip()
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 10.5 * cm, full_name)

    # --- Événement ---
    c.setFillColor(COLOR_TEXT)
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 12.5 * cm, "pour avoir participé à")

    c.setFillColor(COLOR_ACCENT)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 14 * cm, event.title)

    # --- Date ---
    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 12)
    event_date = event.start_at.strftime("%d/%m/%Y")
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 15.5 * cm, f"le {event_date} à {event.city}")

    # --- Référence et code de vérification ---
    c.setFont("Helvetica", 9)
    c.setFillColor(COLOR_MUTED)
    c.drawString(2 * cm, 3 * cm, f"Référence : {certificate.reference}")
    c.drawString(2 * cm, 2.3 * cm, f"Émis le : {certificate.issued_at.strftime('%d/%m/%Y')}")

    # --- QR code en bas à droite ---
    try:
        qr_bytes = generate_qr_image_bytes(certificate.verification_code)
        qr_image = ImageReader(io.BytesIO(qr_bytes))
        qr_size = 3.5 * cm
        c.drawImage(
            qr_image,
            PAGE_WIDTH - qr_size - 2 * cm,
            2 * cm,
            width=qr_size,
            height=qr_size,
        )
        c.setFont("Helvetica", 7)
        c.drawCentredString(
            PAGE_WIDTH - qr_size / 2 - 2 * cm,
            1.5 * cm,
            "Vérifier l'authenticité",
        )
    except Exception as e:
        logger.warning("QR code generation failed | cert=%s | err=%s", certificate.reference, e)

    # --- Finalisation ---
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()