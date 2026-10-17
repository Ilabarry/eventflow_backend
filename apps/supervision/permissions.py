"""
Permissions du module Supervision.

Deux niveaux (décision validée le 17/10) :
    - Admin       : rôle « administrateur » OU is_staff ;
    - Super-admin : is_superuser.

Le backend vérifie TOUJOURS request.user : modifier l'URL ou la requête
dans Angular ne donne aucun droit. Un compte suspendu (is_active=False)
n'a plus aucun accès, même s'il possédait un rôle admin.
"""

import logging

from rest_framework.permissions import BasePermission

from apps.accounts.constants import ROLE_ADMIN

logger = logging.getLogger(__name__)


def is_supervision_admin(user) -> bool:
    """True pour un administrateur actif (standard ou super-admin)."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN)


def is_super_admin(user) -> bool:
    """True uniquement pour un super-administrateur actif."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser


class IsSupervisionAdmin(BasePermission):
    """Accès à /api/supervision/ : administrateurs uniquement."""

    message = "Accès réservé aux administrateurs de la plateforme."

    def has_permission(self, request, view):
        allowed = is_supervision_admin(request.user)
        if not allowed and request.user and request.user.is_authenticated:
            # Journal technique (pas l'AuditLog, pour ne pas le saturer) :
            # un utilisateur connecté tente d'accéder à l'administration.
            logger.warning(
                "Supervision access denied | user=%s | path=%s",
                request.user.id, request.path,
            )
        return allowed


class IsSuperAdmin(BasePermission):
    """Actions critiques (rôles) : super-administrateurs uniquement."""

    message = "Action réservée aux super-administrateurs."

    def has_permission(self, request, view):
        return is_super_admin(request.user)
