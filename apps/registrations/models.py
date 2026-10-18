"""
Modèle Registration pour EVENTFLOW.

Représente l'inscription d'un participant à un événement.

Décisions clés :
    - UUID comme clé primaire
    - Référence unique lisible (EVF-REG-YYYY-XXXXXX)
    - Soft delete : status=CANCELLED (pas de suppression physique)
    - UniqueConstraint conditionnelle : empêche la double inscription active
    - Pas de FK vers TicketType (sera ajoutée plus tard)
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.events.models import Event
from apps.registrations.constants import (
    ACTIVE_STATUSES,
    ALLOWED_STATUS_TRANSITIONS,
    REFERENCE_MAX_LENGTH,
    RegistrationStatus,
)


class Registration(models.Model):
    """
    Inscription d'un participant à un événement.

    Attributs principaux :
        - participant : l'utilisateur qui s'inscrit
        - event : l'événement concerné
        - reference : identifiant lisible unique (EVF-REG-YYYY-XXXXXX)
        - status : PENDING, CONFIRMED ou CANCELLED

    Règles métier :
        - Un participant ne peut avoir qu'UNE inscription active
          par événement (contrainte DB conditionnelle).
        - Une inscription annulée reste en base (historique).
        - Le statut initial dépend du type d'événement :
            - FREE   → CONFIRMED immédiatement
            - PAID   → PENDING (en attendant Payment)
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
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="Participant",
        help_text="Utilisateur inscrit à l'événement.",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="Événement",
        help_text="Événement concerné par l'inscription.",
    )

        # ------------------------------------------------------------------
    # Type de ticket (optionnel pour événements gratuits)
    # ------------------------------------------------------------------
    ticket_type = models.ForeignKey(
        "tickets.TicketType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="registrations",
        verbose_name="Type de ticket",
        help_text="Obligatoire pour les événements payants avec types de tickets.",
    )

    # ------------------------------------------------------------------
    # Prix réellement payé (snapshot au moment de la confirmation)
    # ------------------------------------------------------------------
    price_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix payé",
        help_text="Prix réel payé (snapshot, ne change pas si TicketType change).",
    )

    # ------------------------------------------------------------------
    # Référence unique
    # ------------------------------------------------------------------
    reference = models.CharField(
        max_length=REFERENCE_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name="Référence",
        help_text="Référence unique lisible (ex: EVF-REG-2026-A8K3X2).",
    )

    # ------------------------------------------------------------------
    # Statut
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.PENDING,
        db_index=True,
        verbose_name="Statut",
    )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    registered_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Date d'inscription",
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

    # ------------------------------------------------------------------
    # Méta
    # ------------------------------------------------------------------
    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        ordering = ["-registered_at"]
        constraints = [
            # Empêche la double inscription active (PENDING ou CONFIRMED)
            # pour un même participant sur un même événement.
            # Les inscriptions CANCELLED sont ignorées (index partiel PostgreSQL).
            models.UniqueConstraint(
                fields=["participant", "event"],
                condition=~models.Q(status=RegistrationStatus.CANCELLED),
                name="unique_active_registration_per_event",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="idx_reg_event_status"),
            models.Index(fields=["participant", "status"], name="idx_reg_participant_status"),
            models.Index(fields=["-registered_at"], name="idx_reg_registered_desc"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.participant} → {self.event}"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def is_pending(self) -> bool:
        return self.status == RegistrationStatus.PENDING

    @property
    def is_confirmed(self) -> bool:
        return self.status == RegistrationStatus.CONFIRMED

    @property
    def is_cancelled(self) -> bool:
        return self.status == RegistrationStatus.CANCELLED

    @property
    def is_active(self) -> bool:
        """Une inscription active occupe une place dans l'événement."""
        return self.status in ACTIVE_STATUSES

    # ------------------------------------------------------------------
    # Méthodes métier
    # ------------------------------------------------------------------
    def can_transition_to(self, new_status: str) -> bool:
        """Vérifie si une transition de statut est autorisée."""
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def can_be_cancelled(self) -> bool:
        """Une inscription peut être annulée si elle n'est pas déjà CANCELLED."""
        return self.status != RegistrationStatus.CANCELLED