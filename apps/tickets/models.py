"""
Modèles du module Tickets : TicketType et Ticket.

Distinction fondamentale :
    - TicketType : type/modèle de billet (ex: Standard, VIP).
    - Ticket     : billet individuel émis pour un participant.
"""

import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.events.models import Event
from apps.registrations.models import Registration
from apps.tickets.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    CURRENCY_CODE_LENGTH,
    DEFAULT_CURRENCY,
    PRICE_DECIMAL_PLACES,
    PRICE_MAX_DIGITS,
    REFERENCE_MAX_LENGTH,
    TicketStatus,
)


# ==================================================================
# MODÈLE : TicketType
# ==================================================================
class TicketType(models.Model):
    """
    Type de ticket proposé pour un événement.

    Exemple : "Standard", "VIP", "Premium".
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="ticket_types",
        verbose_name="Événement",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nom du type de ticket",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    price = models.DecimalField(
        max_digits=PRICE_MAX_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Prix",
    )
    currency = models.CharField(
        max_length=CURRENCY_CODE_LENGTH,
        default=DEFAULT_CURRENCY,
        verbose_name="Devise",
    )
    quantity_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Quantité totale",
        help_text="NULL = illimité.",
    )
    quantity_sold = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantité vendue",
    )
    sales_start_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Début des ventes",
    )
    sales_end_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fin des ventes",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour",
    )

    class Meta:
        verbose_name = "Type de ticket"
        verbose_name_plural = "Types de tickets"
        ordering = ["event", "price"]
        constraints = [
            # quantity_sold <= quantity_total (si quantity_total défini)
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_total__isnull=True)
                    | models.Q(quantity_sold__lte=models.F("quantity_total"))
                ),
                name="ticket_type_quantity_consistent",
            ),
            # sales_start_at < sales_end_at (si les deux définis)
            models.CheckConstraint(
                condition=(
                    models.Q(sales_start_at__isnull=True)
                    | models.Q(sales_end_at__isnull=True)
                    | models.Q(sales_start_at__lt=models.F("sales_end_at"))
                ),
                name="ticket_type_sales_window_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "is_active"], name="idx_tt_event_active"),
            models.Index(fields=["price"], name="idx_tt_price"),
        ]

    def __str__(self):
        return f"{self.name} ({self.event.title})"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def is_unlimited(self) -> bool:
        return self.quantity_total is None

    @property
    def available_quantity(self) -> int | None:
        """Nombre de places restantes (None si illimité)."""
        if self.is_unlimited:
            return None
        return max(0, self.quantity_total - self.quantity_sold)

    @property
    def is_sold_out(self) -> bool:
        """True si la quantité est atteinte."""
        if self.is_unlimited:
            return False
        return self.quantity_sold >= self.quantity_total

    def is_on_sale(self, at=None) -> bool:
        """
        Vérifie si le TicketType est actuellement en vente.

        Args:
            at: Date de référence (défaut: maintenant).
        """
        at = at or timezone.now()
        if not self.is_active:
            return False
        if self.sales_start_at and at < self.sales_start_at:
            return False
        if self.sales_end_at and at > self.sales_end_at:
            return False
        return True


# ==================================================================
# MODÈLE : Ticket
# ==================================================================
class Ticket(models.Model):
    """
    Ticket individuel émis pour un participant.

    Relation :
        Registration 1 ──── 0..1 Ticket
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    registration = models.OneToOneField(
        Registration,
        on_delete=models.CASCADE,
        related_name="ticket",
        verbose_name="Inscription",
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
        verbose_name="Type de ticket",
    )
    reference = models.CharField(
        max_length=REFERENCE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name="Référence",
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.VALID,
        db_index=True,
        verbose_name="Statut",
    )
    issued_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Date d'émission",
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'utilisation",
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'annulation",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour",
    )

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["ticket_type", "status"], name="idx_tkt_tt_status"),
            models.Index(fields=["-issued_at"], name="idx_tkt_issued_desc"),
        ]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def is_valid(self) -> bool:
        return self.status == TicketStatus.VALID

    @property
    def is_used(self) -> bool:
        return self.status == TicketStatus.USED

    @property
    def is_cancelled(self) -> bool:
        return self.status == TicketStatus.CANCELLED

    @property
    def is_expired(self) -> bool:
        return self.status == TicketStatus.EXPIRED

    # ------------------------------------------------------------------
    # Méthodes métier
    # ------------------------------------------------------------------
    def can_transition_to(self, new_status: str) -> bool:
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def can_be_cancelled(self) -> bool:
        return self.status == TicketStatus.VALID