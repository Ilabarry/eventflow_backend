"""
Modèle Payment pour EVENTFLOW.

Représente une transaction financière liée à une inscription.

Décisions clés :
    - UUID comme clé primaire
    - Référence interne unique (EVF-PAY-YYYY-XXXXXX)
    - DecimalField pour les montants (jamais float)
    - Contrainte conditionnelle : un seul SUCCESS par Registration
    - support d'idempotency_key
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.payments.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    AMOUNT_DECIMAL_PLACES,
    AMOUNT_MAX_DIGITS,
    CURRENCY_CODE_LENGTH,
    DEFAULT_CURRENCY,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    REFERENCE_MAX_LENGTH,
)
from apps.registrations.models import Registration


class Payment(models.Model):
    """
    Transaction financière liée à une inscription.

    Une inscription peut avoir plusieurs paiements (tentatives), mais
    une seule transaction SUCCESS (contrainte DB conditionnelle).
    """

    # ------------------------------------------------------------------
    # Identifiant
    # ------------------------------------------------------------------
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------
    registration = models.ForeignKey(
        Registration,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="Inscription",
        help_text="Inscription à laquelle ce paiement est rattaché.",
    )

    # ------------------------------------------------------------------
    # Montant et devise
    # ------------------------------------------------------------------
    amount = models.DecimalField(
        max_digits=AMOUNT_MAX_DIGITS,
        decimal_places=AMOUNT_DECIMAL_PLACES,
        verbose_name="Montant",
        help_text="Montant calculé côté backend (jamais fourni par le client).",
    )
    currency = models.CharField(
        max_length=CURRENCY_CODE_LENGTH,
        default=DEFAULT_CURRENCY,
        verbose_name="Devise",
        help_text="Code ISO 4217 de la devise (ex: XOF, EUR, USD).",
    )

    # ------------------------------------------------------------------
    # Méthode et provider
    # ------------------------------------------------------------------
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name="Méthode de paiement",
    )
    provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        verbose_name="Fournisseur",
    )

    # ------------------------------------------------------------------
    # Références
    # ------------------------------------------------------------------
    transaction_reference = models.CharField(
        max_length=REFERENCE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name="Référence interne",
        help_text="Référence unique EVENTFLOW (ex: EVF-PAY-2026-A8K3X2).",
    )
    provider_reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Référence provider",
        help_text="Référence externe renvoyée par le prestataire.",
    )

    # ------------------------------------------------------------------
    # Statut
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        verbose_name="Statut",
    )

    # ------------------------------------------------------------------
    # Informations d'échec
    # ------------------------------------------------------------------
    failure_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Code d'échec",
        help_text="Code technique d'échec (ex: INSUFFICIENT_FUNDS).",
    )
    failure_message = models.TextField(
        blank=True,
        default="",
        verbose_name="Message d'échec",
        help_text="Message complet d'échec (pour le support).",
    )

    # ------------------------------------------------------------------
    # Idempotence
    # ------------------------------------------------------------------
    idempotency_key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Clé d'idempotence",
        help_text="Clé fournie par le client pour éviter les doubles paiements.",
    )

    # ------------------------------------------------------------------
    # Métadonnées
    # ------------------------------------------------------------------
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Métadonnées",
        help_text="Données non sensibles (JSON).",
    )

    # ------------------------------------------------------------------
    # Dates clés
    # ------------------------------------------------------------------
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de paiement",
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'annulation",
    )
    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de remboursement",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
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
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-created_at"]
        constraints = [
            # Un seul paiement SUCCESS par Registration.
            # Les autres statuts (FAILED, CANCELLED...) peuvent coexister.
            models.UniqueConstraint(
                fields=["registration"],
                condition=models.Q(status=PaymentStatus.SUCCESS),
                name="unique_successful_payment_per_registration",
            ),
        ]
        indexes = [
            models.Index(fields=["registration", "status"], name="idx_pay_reg_status"),
            models.Index(fields=["status", "-created_at"], name="idx_pay_status_created"),
            models.Index(fields=["-created_at"], name="idx_pay_created_desc"),
        ]

    def __str__(self):
        return f"{self.transaction_reference} — {self.amount} {self.currency} ({self.status})"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def is_pending(self) -> bool:
        return self.status == PaymentStatus.PENDING

    @property
    def is_success(self) -> bool:
        return self.status == PaymentStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == PaymentStatus.FAILED

    @property
    def is_cancelled(self) -> bool:
        return self.status == PaymentStatus.CANCELLED

    @property
    def is_refunded(self) -> bool:
        return self.status == PaymentStatus.REFUNDED

    @property
    def is_terminal(self) -> bool:
        """Un statut terminal ne peut plus évoluer."""
        return self.status in (
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.REFUNDED,
        )

    # ------------------------------------------------------------------
    # Méthodes métier
    # ------------------------------------------------------------------
    def can_transition_to(self, new_status: str) -> bool:
        """Vérifie si la transition de statut est autorisée."""
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def can_be_cancelled(self) -> bool:
        """Un paiement n'est annulable que s'il est PENDING."""
        return self.status == PaymentStatus.PENDING

    def can_be_refunded(self) -> bool:
        """Un paiement n'est remboursable que s'il est SUCCESS."""
        return self.status == PaymentStatus.SUCCESS