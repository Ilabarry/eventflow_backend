import uuid

from django.db import models


class Certificate(models.Model):
    """Représente un certificat de participation à un événement."""
"""
Modèle Certificate pour EVENTFLOW.

Un certificat est émis pour une inscription après vérification de
l'éligibilité (Registration CONFIRMED + Attendance PRESENT + Event terminé).
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
    """
    Certificat de participation lié à une inscription.

    Relation :
        Registration 1 ──── 0..1 Certificate
    """

    # ------------------------------------------------------------------
    # Identifiant
    # ------------------------------------------------------------------
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    pdf_file = models.FileField(
        upload_to="certificates/",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificat {self.reference}"
        verbose_name="Identifiant",

    # ------------------------------------------------------------------
    # Relation
    # ------------------------------------------------------------------
    registration = models.OneToOneField(
        Registration,
        on_delete=models.CASCADE,
        related_name="certificate",
        verbose_name="Inscription",
    )

    # ------------------------------------------------------------------
    # Référence et code de vérification
    # ------------------------------------------------------------------
    reference = models.CharField(
        max_length=REFERENCE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name="Référence",
    )
    verification_code = models.CharField(
        max_length=VERIFICATION_CODE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name="Code de vérification",
    )

    # ------------------------------------------------------------------
    # Statut
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=CertificateStatus.choices,
        default=CertificateStatus.PENDING,
        db_index=True,
        verbose_name="Statut",
    )

    # ------------------------------------------------------------------
    # Fichier PDF
    # ------------------------------------------------------------------
    pdf_file = models.FileField(
        upload_to="certificates/%Y/",
        null=True,
        blank=True,
        verbose_name="Fichier PDF",
    )

    # ------------------------------------------------------------------
    # Dates et traçabilité
    # ------------------------------------------------------------------
    issued_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Date d'émission",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de révocation",
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_certificates",
        verbose_name="Révoqué par",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour",
    )

    # ------------------------------------------------------------------
    # Méta
    # ------------------------------------------------------------------
    class Meta:
        verbose_name = "Certificat"
        verbose_name_plural = "Certificats"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["status", "-issued_at"], name="idx_cert_status_issued"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.registration.participant.full_name}"

    # ------------------------------------------------------------------
    # Propriétés
    # ------------------------------------------------------------------
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
        """Un certificat est valide s'il est ISSUED (pas révoqué)."""
        return self.status == CertificateStatus.ISSUED

    # ------------------------------------------------------------------
    # Méthodes métier
    # ------------------------------------------------------------------
    def can_transition_to(self, new_status: str) -> bool:
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed
        return new_status in allowed
