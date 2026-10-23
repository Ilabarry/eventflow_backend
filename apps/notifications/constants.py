"""
Constantes et enums du module Notifications.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationType(models.TextChoices):
    """Types de notifications métier."""
    REGISTRATION = "REGISTRATION", _("Inscription")
    EVENT_UPDATE = "EVENT_UPDATE", _("Modification d'un événement")
    EVENT_PUBLICATION = "EVENT_PUBLICATION", _("Publication d'un événement")
    REMINDER = "REMINDER", _("Rappel")
    TICKET = "TICKET", _("Billetterie")
    PAYMENT = "PAYMENT", _("Paiement")
    ATTENDANCE = "ATTENDANCE", _("Présence")
    CERTIFICATE = "CERTIFICATE", _("Certificat")
    SYSTEM = "SYSTEM", _("Système")


class NotificationChannel(models.TextChoices):
    """
    Canaux de diffusion (V1 : IN_APP uniquement).
    Les autres canaux sont préparés pour la V2.
    """
    IN_APP = "IN_APP", _("In-app")
    EMAIL = "EMAIL", _("Email")
    SMS = "SMS", _("SMS")
    PUSH = "PUSH", _("Push")


# Longueurs maximales
TITLE_MAX_LENGTH = 200
TYPE_MAX_LENGTH = 30
RELATED_ENTITY_TYPE_MAX_LENGTH = 50
RELATED_ENTITY_ID_MAX_LENGTH = 64