"""
Services métier du module Supervision.

Phase S1 : AuditService, utilisé par toutes les actions administratives.

Règle d'usage : chaque service d'action appelle AuditService.log() DANS
SA transaction (transaction.atomic). Ainsi, soit l'action ET sa trace
sont enregistrées, soit aucune des deux : jamais d'action sans trace.
"""

import logging

from apps.supervision.constants import (
    FILTERED_VALUE,
    SENSITIVE_EXACT_KEYS,
    SENSITIVE_KEY_FRAGMENTS,
    USER_AGENT_MAX_LENGTH,
    AuditResult,
)
from apps.supervision.models import AuditLog

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Nettoyage des métadonnées
# ------------------------------------------------------------------
def _is_sensitive_key(key) -> bool:
    name = str(key).lower()
    return name in SENSITIVE_EXACT_KEYS or any(f in name for f in SENSITIVE_KEY_FRAGMENTS)


def sanitize_metadata(value):
    """
    Remplace par « [FILTRÉ] » toute valeur dont la clé semble sensible
    (mot de passe, jeton, secret, carte...), à toutes les profondeurs
    du dictionnaire. Un secret ne doit JAMAIS atteindre la base d'audit.
    """
    if isinstance(value, dict):
        return {
            key: FILTERED_VALUE if _is_sensitive_key(key) else sanitize_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_metadata(item) for item in value]
    return value


# ------------------------------------------------------------------
# Contexte réseau de la requête
# ------------------------------------------------------------------
def get_client_ip(request):
    """
    Adresse IP de la requête.

    On utilise REMOTE_ADDR et PAS l'en-tête X-Forwarded-For : ce dernier
    est fourni par le client et peut être falsifié. Si l'application est
    un jour derrière un proxy de confiance (Nginx), il faudra le
    configurer explicitement.
    """
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


def get_user_agent(request) -> str:
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:USER_AGENT_MAX_LENGTH]


# ------------------------------------------------------------------
# Service d'audit
# ------------------------------------------------------------------
class AuditService:
    """Écriture dans le journal d'audit (le seul point d'entrée)."""

    @staticmethod
    def log(
        *,
        actor,
        action: str,
        entity_type: str,
        entity_id="",
        description: str,
        reason: str = "",
        metadata: dict | None = None,
        result: str = AuditResult.SUCCESS,
        request=None,
    ) -> AuditLog:
        """
        Enregistre une entrée d'audit.

        Args:
            actor: l'utilisateur qui agit (request.user).
            action / entity_type: valeurs de AuditAction / AuditEntity.
            entity_id: identifiant de la ressource visée.
            description: phrase lisible (« Suspension de awa@test.com »).
            reason: raison saisie par l'administrateur.
            metadata: détails complémentaires (nettoyés automatiquement).
            result: SUCCESS ou DENIED.
            request: requête HTTP, pour l'IP et le navigateur.
        """
        entry = AuditLog.objects.create(
            actor=actor if getattr(actor, "pk", None) else None,
            actor_email=getattr(actor, "email", "") or "",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ""),
            description=description,
            reason=reason or "",
            metadata=sanitize_metadata(metadata or {}),
            result=result,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        # Journal technique : identifiants uniquement, pas de contenu.
        logger.info(
            "Audit | action=%s | entity=%s:%s | actor=%s | result=%s",
            action, entity_type, entity_id, getattr(actor, "pk", None), result,
        )
        return entry
