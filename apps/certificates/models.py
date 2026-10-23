
"""
Modèle Certificate pour EVENTFLOW.

Un certificat est émis pour une inscription après vérification de
l'éligibilité (Registration CONFIRMED + Attendance PRESENT + Event terminé).

Relation :
    Registration 1 ──── 0..1 Certificate
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.certificates.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    REFERENCE_MAX_LENGTH,
    VERIFICATION_CODE_MAX_LENGTH,
    CertificateStatus,
)
from apps.registrations.models import Registration


class Certificate(models.Model):
    """Certificat de participation lié à une inscription."""

    # Identifiant unique du certificat
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("Identifiant"),
    )


    # Relation : une inscription possède au maximum un certificat
    # ------------------------------------------------------------------
    # Relation
    # ------------------------------------------------------------------
    registration = models.OneToOneField(
        Registration,
        on_delete=models.CASCADE,
        related_name="certificate",
        verbose_name=_("Inscription"),
    )

    # Référence et code de vérification
    reference = models.CharField(
        max_length=REFERENCE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name=_("Référence"),
    )
    verification_code = models.CharField(
        max_length=VERIFICATION_CODE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name=_("Code de vérification"),
    )

    # Statut du certificat
    status = models.CharField(
        max_length=20,
        choices=CertificateStatus.choices,
        default=CertificateStatus.PENDING,
        db_index=True,
        verbose_name=_("Statut"),
    )

    # Fichier PDF associé
    pdf_file = models.FileField(
        upload_to="certificates/%Y/",
        null=True,
        blank=True,
        verbose_name=_("Fichier PDF"),
    )

    # Dates et traçabilité
    issued_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Date d'émission"),
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date de révocation"),
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_certificates",
        verbose_name=_("Révoqué par"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Date de mise à jour"),
    )

    class Meta:
        verbose_name = _("Certificat")
        verbose_name_plural = _("Certificats")
        ordering = ["-issued_at"]
        indexes = [
            models.Index(
                fields=["status", "-issued_at"],
                name="idx_cert_status_issued",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.registration.participant.full_name}"

    @property
    def is_pending(self) -> bool:
        return self.status == CertificateStatus.PENDING

    @property
    def is_issued(self) -> bool:
        return self.status == CertificateStatus.ISSUED

    @property
    def is_revoked(self) -> bool:
        return self.status == CertificateStatus.REVOKED

    @property
    def is_valid(self) -> bool:
        """Un certificat est valide lorsque son statut est ISSUED."""
        return self.status == CertificateStatus.ISSUED

    def can_transition_to(self, new_status: str) -> bool:
        """Vérifie si le changement de statut est autorisé."""
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed
        return new_status in allowed
