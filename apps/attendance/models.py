"""
Modèle Attendance pour EVENTFLOW.

Représente la présence (ou l'absence déclarée) d'un participant
à un événement, à travers son inscription.

Décisions clés :
    - UUID comme clé primaire (convention EVENTFLOW).
    - OneToOne vers Registration : une inscription a AU PLUS une fiche
      de présence. La contrainte d'unicité est garantie par PostgreSQL,
      ce qui bloque le double check-in même en cas de requêtes simultanées.
    - L'événement et le participant ne sont PAS stockés ici : ils sont
      déduits de Registration (une seule source de vérité, pas de risque
      d'incohérence).
    - La logique de check-in est dans services.py (phase 2), pas ici.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.attendance.constants import (
    CHECK_IN_METHOD_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    AttendanceStatus,
    CheckInMethod,
)
from apps.registrations.models import Registration


class Attendance(models.Model):
    """
    Fiche de présence liée à une inscription.

    Règles métier :
        - PRESENT : checked_in_at et check_in_method sont obligatoires.
        - ABSENT  : checked_in_at et check_in_method sont vides.
        - Pas de fiche = participant inscrit, pas encore arrivé.
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
    # OneToOne = ForeignKey + contrainte UNIQUE en base.
    # PROTECT : les inscriptions ne sont jamais supprimées dans EVENTFLOW
    # (elles passent en CANCELLED). Si quelqu'un tente quand même de
    # supprimer une inscription qui a une présence, PostgreSQL refuse :
    # l'historique de présence (futurs certificats) est préservé.
    registration = models.OneToOneField(
        Registration,
        on_delete=models.PROTECT,
        related_name="attendance",
        verbose_name="Inscription",
        help_text="Inscription concernée par cette fiche de présence.",
    )

    # Traçabilité : qui a enregistré cette fiche (check-in ou absence).
    # SET_NULL : si ce compte est supprimé, la présence reste valable.
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendances",
        verbose_name="Enregistré par",
        help_text="Organisateur ou administrateur ayant enregistré la fiche.",
    )

    # ------------------------------------------------------------------
    # Présence
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=STATUS_MAX_LENGTH,
        choices=AttendanceStatus.choices,
        verbose_name="Statut",
    )
    checked_in_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date et heure du check-in",
    )
    check_in_method = models.CharField(
        max_length=CHECK_IN_METHOD_MAX_LENGTH,
        choices=CheckInMethod.choices,
        null=True,
        blank=True,
        verbose_name="Méthode de check-in",
    )

    # ------------------------------------------------------------------
    # Dates techniques
    # ------------------------------------------------------------------
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
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        ordering = ["-created_at"]
        constraints = [
            # Garantit en base qu'une fiche est toujours cohérente :
            # un PRESENT sans heure de check-in, ou un ABSENT avec une
            # méthode de check-in, serait une donnée contradictoire.
            # Même une erreur de code ou une saisie dans l'admin ne
            # pourra pas enregistrer une telle ligne.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=AttendanceStatus.PRESENT,
                        checked_in_at__isnull=False,
                        check_in_method__isnull=False,
                    )
                    | models.Q(
                        status=AttendanceStatus.ABSENT,
                        checked_in_at__isnull=True,
                        check_in_method__isnull=True,
                    )
                ),
                name="attendance_status_consistency",
            ),
        ]
        indexes = [
            # Sert aux statistiques et aux filtres : « les présents,
            # triés par heure d'arrivée ». registration a déjà son
            # propre index (créé par la contrainte UNIQUE du OneToOne).
            models.Index(
                fields=["status", "checked_in_at"],
                name="idx_att_status_checkin",
            ),
        ]

    def __str__(self):
        return f"{self.registration.reference} — {self.get_status_display()}"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def is_present(self) -> bool:
        return self.status == AttendanceStatus.PRESENT

    @property
    def is_absent(self) -> bool:
        return self.status == AttendanceStatus.ABSENT
