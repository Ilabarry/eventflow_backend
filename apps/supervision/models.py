"""
Modèle du module Supervision : AuditLog (journal d'audit).

C'est la SEULE table propre à supervision : toutes les autres données
supervisées appartiennent à leurs modules (accounts, events...).

Le journal répond à : QUI a fait QUOI, sur QUELLE ressource, QUAND,
depuis QUELLE adresse, POURQUOI (raison) et avec QUEL résultat.

Règle d'or : un journal d'audit est en AJOUT SEUL. Une ligne écrite ne
doit jamais être modifiée ni supprimée par l'application, sinon il ne
prouve plus rien.
"""

import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

from apps.supervision.constants import (
    ACTION_MAX_LENGTH,
    ENTITY_ID_MAX_LENGTH,
    ENTITY_TYPE_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    AuditAction,
    AuditEntity,
    AuditResult,
)

IMMUTABLE_MESSAGE = "Le journal d'audit est en lecture seule : modification et suppression interdites."


class AuditLogQuerySet(models.QuerySet):
    """
    Bloque les modifications et suppressions EN MASSE
    (AuditLog.objects.filter(...).update(...) / .delete()).
    """

    def update(self, **kwargs):
        raise PermissionDenied(IMMUTABLE_MESSAGE)

    def delete(self):
        raise PermissionDenied(IMMUTABLE_MESSAGE)


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ------------------------------------------------------------------
    # QUI
    # ------------------------------------------------------------------
    # SET_NULL : si le compte de l'admin est supprimé un jour, la trace
    # reste ; actor_email garde une copie figée de son identité.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Acteur",
    )
    actor_email = models.EmailField(blank=True, verbose_name="E-mail de l'acteur")

    # ------------------------------------------------------------------
    # QUOI / SUR QUOI
    # ------------------------------------------------------------------
    action = models.CharField(
        max_length=ACTION_MAX_LENGTH, choices=AuditAction.choices, verbose_name="Action",
    )
    entity_type = models.CharField(
        max_length=ENTITY_TYPE_MAX_LENGTH, choices=AuditEntity.choices, verbose_name="Type de ressource",
    )
    # Texte (et non UUIDField) : reste compatible avec toute future ressource.
    entity_id = models.CharField(
        max_length=ENTITY_ID_MAX_LENGTH, blank=True, verbose_name="Identifiant de la ressource",
    )
    description = models.TextField(verbose_name="Description")
    reason = models.TextField(blank=True, verbose_name="Raison invoquée")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées (nettoyées)")
    result = models.CharField(
        max_length=10, choices=AuditResult.choices, default=AuditResult.SUCCESS, verbose_name="Résultat",
    )

    # ------------------------------------------------------------------
    # D'OÙ / QUAND
    # ------------------------------------------------------------------
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    user_agent = models.CharField(max_length=USER_AGENT_MAX_LENGTH, blank=True, verbose_name="Navigateur")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Date")

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        verbose_name = "Entrée du journal d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ["-created_at"]
        indexes = [
            # « Que s'est-il passé sur cette ressource ? »
            models.Index(fields=["entity_type", "entity_id"], name="idx_audit_entity"),
            # « Toutes les suspensions du mois »
            models.Index(fields=["action", "-created_at"], name="idx_audit_action_date"),
            # « Tout ce qu'a fait cet admin »
            models.Index(fields=["actor", "-created_at"], name="idx_audit_actor_date"),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_email} {self.action}"

    # ------------------------------------------------------------------
    # Immutabilité (niveau application)
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        # _state.adding vaut False pour une ligne déjà enregistrée :
        # on autorise la création, jamais la modification.
        if not self._state.adding:
            raise PermissionDenied(IMMUTABLE_MESSAGE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(IMMUTABLE_MESSAGE)
