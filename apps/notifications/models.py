
"""
Modèles de données du module Notifications d'EVENTFLOW.

Ce module gère les notifications internes destinées aux utilisateurs.
Les envois par email, SMS et notifications push seront développés
ultérieurement, dans des composants séparés.
"""

import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Représente une notification destinée à un utilisateur."""

    class Type(models.TextChoices):
        REGISTRATION = "REGISTRATION", "Inscription"
        EVENT_UPDATE = "EVENT_UPDATE", "Modification d'un événement"
        EVENT_PUBLICATION = "EVENT_PUBLICATION", "Publication d'un événement"
        REMINDER = "REMINDER", "Rappel"
        TICKET = "TICKET", "Billetterie"
        PAYMENT = "PAYMENT", "Paiement"
        ATTENDANCE = "ATTENDANCE", "Présence"
        CERTIFICATE = "CERTIFICATE", "Certificat"
        SYSTEM = "SYSTEM", "Système"

    # Identifiant unique de la notification.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Utilisateur qui reçoit la notification.
    # OnDelete CASCADE : ses notifications sont supprimées avec son compte.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    title = models.CharField(max_length=200)
    message = models.TextField()

    type = models.CharField(
        max_length=30,
        choices=Type.choices,
        default=Type.SYSTEM,
    )

    # État de lecture.
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Référence facultative à un objet du projet :
    # événement, inscription, billet, paiement, etc.
    related_entity_type = models.CharField(
        max_length=50,
        blank=True,
    )
    related_entity_id = models.CharField(
        max_length=64,
        blank=True,
    )

    # Informations complémentaires destinées notamment à Angular.
    # Exemple : {"url": "/events/123"}.
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="notif_user_created_idx",
            ),
            models.Index(
                fields=["user", "is_read"],
                name="notif_user_read_idx",
            ),
            models.Index(
                fields=["type"],
                name="notif_type_idx",
            ),
        ]

    def __str__(self):
        """Représentation lisible dans Django Admin et les journaux."""
        return f"{self.title} — {self.user}"
