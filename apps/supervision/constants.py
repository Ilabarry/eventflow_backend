"""
Constantes du module Supervision (administration d'EVENTFLOW).

Toutes les valeurs d'audit sont centralisées ici : aucun service ne doit
écrire une action « en dur » (risque de fautes de frappe et de journaux
impossibles à filtrer).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# AUDIT : actions tracées
# ==================================================================
class AuditAction(models.TextChoices):
    """
    Actions administratives enregistrées dans le journal d'audit.

    Seules les actions réellement implémentées figurent ici. Les actions
    des modules futurs (PAYMENT_REFUNDED, CERTIFICATE_REVOKED...) seront
    ajoutées quand ces modules existeront.
    """
    # Utilisateurs
    USER_SUSPENDED = "USER_SUSPENDED", _("Utilisateur suspendu")
    USER_ACTIVATED = "USER_ACTIVATED", _("Utilisateur réactivé")
    # Rôles
    ROLE_GRANTED = "ROLE_GRANTED", _("Rôle attribué")
    ROLE_REVOKED = "ROLE_REVOKED", _("Rôle retiré")
    # Événements
    EVENT_PUBLISHED = "EVENT_PUBLISHED", _("Événement publié")
    EVENT_CANCELLED = "EVENT_CANCELLED", _("Événement annulé")
    # Catégories
    CATEGORY_CREATED = "CATEGORY_CREATED", _("Catégorie créée")
    CATEGORY_UPDATED = "CATEGORY_UPDATED", _("Catégorie modifiée")
    CATEGORY_DEACTIVATED = "CATEGORY_DEACTIVATED", _("Catégorie désactivée")
    CATEGORY_ACTIVATED = "CATEGORY_ACTIVATED", _("Catégorie réactivée")
    CATEGORY_DELETED = "CATEGORY_DELETED", _("Catégorie supprimée")


# ==================================================================
# AUDIT : types de ressources concernées
# ==================================================================
class AuditEntity(models.TextChoices):
    USER = "USER", _("Utilisateur")
    ROLE = "ROLE", _("Rôle")
    EVENT = "EVENT", _("Événement")
    CATEGORY = "CATEGORY", _("Catégorie")


# ==================================================================
# AUDIT : résultat de l'action
# ==================================================================
class AuditResult(models.TextChoices):
    """
    SUCCESS : l'action a été effectuée.
    DENIED  : l'action a été refusée par un garde-fou de sécurité
              (ex. tentative de suspendre le dernier administrateur).
    """
    SUCCESS = "SUCCESS", _("Réussie")
    DENIED = "DENIED", _("Refusée")


# ==================================================================
# AUDIT : nettoyage des métadonnées
# ==================================================================
# Toute clé dont le nom CONTIENT l'un de ces fragments est masquée.
SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "authorization",
    "cvv",
    "card",
    "iban",
)
# Clés masquées uniquement si le nom est EXACTEMENT celui-ci
# (trop courtes pour une recherche par fragment : « pin » est dans « shipping »).
SENSITIVE_EXACT_KEYS = ("pin", "otp", "pan", "access", "refresh")
FILTERED_VALUE = "[FILTRÉ]"

USER_AGENT_MAX_LENGTH = 255
ACTION_MAX_LENGTH = 50
ENTITY_TYPE_MAX_LENGTH = 30
ENTITY_ID_MAX_LENGTH = 64


# ==================================================================
# LIMITATION DU DÉBIT (throttling)
# ==================================================================
# Noms des « scopes » ; les débits sont définis dans settings.py.
THROTTLE_SCOPE_READ = "supervision_read"
THROTTLE_SCOPE_ACTION = "supervision_action"


# ==================================================================
# ACTIONS SUR LES COMPTES (phase S2)
# ==================================================================
# Raison obligatoire pour suspendre ou réactiver un compte.
REASON_MIN_LENGTH = 5
REASON_MAX_LENGTH = 500

# Nombre d'éléments récents affichés par rubrique dans /activity/.
ACTIVITY_PREVIEW_SIZE = 10
