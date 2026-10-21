"""
Modèles de données du module Notifications d'EVENTFLOW.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.notifications.constants import (
    RELATED_ENTITY_ID_MAX_LENGTH,
    RELATED_ENTITY_TYPE_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    TYPE_MAX_LENGTH,
    NotificationType,
)


class Notification(models.Model):
    """Représente une notification destinée à un utilisateur."""

    # ------------------------------------------------------------------
    # Identifiant
    # ------------------------------------------------------------------
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # ------------------------------------------------------------------
    # Destinataire
    # ------------------------------------------------------------------
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    # ------------------------------------------------------------------
    # Contenu
    # ------------------------------------------------------------------
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    message = models.TextField()

    type = models.CharField(
        max_length=TYPE_MAX_LENGTH,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
    )

    # ------------------------------------------------------------------
    # État de lecture
    # ------------------------------------------------------------------
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # ------------------------------------------------------------------
    # Référence polymorphe (découplée)
    # ------------------------------------------------------------------
    related_entity_type = models.CharField(
        max_length=RELATED_ENTITY_TYPE_MAX_LENGTH,
        blank=True,
    )
    related_entity_id = models.CharField(
        max_length=RELATED_ENTITY_ID_MAX_LENGTH,
        blank=True,
    )

    # ------------------------------------------------------------------
    # Métadonnées (URL Angular, etc.)
    # ------------------------------------------------------------------
    metadata = models.JSONField(default=dict, blank=True)

    # ------------------------------------------------------------------
    # Date
    # ------------------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="notif_user_created_idx"),
            models.Index(fields=["user", "is_read"], name="notif_user_read_idx"),
            models.Index(fields=["type"], name="notif_type_idx"),
        ]

    def __str__(self):
        return f"{self.title} — {self.user}"