"""
Garde-fous anti-escalade du module Supervision.

Ces fonctions ne modifient rien : elles vérifient une règle et lèvent
une exception SecurityGuardDenied si elle n'est pas respectée.

Règles (phase S2, suspension / réactivation) :
    1. l'auteur doit être un administrateur ACTIF au moment de l'action ;
    2. personne ne change le statut de son propre compte ;
    3. seul un super-admin agit sur un compte administrateur ;
    4. on ne suspend jamais le dernier administrateur actif.
"""

from django.db.models import Q

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.supervision.exceptions import (
    ActorNoLongerAdmin,
    AdminTargetRequiresSuperAdmin,
    CannotChangeOwnStatus,
    LastActiveAdmin,
)

# Un compte « administrateur » : même définition que permissions.py.
ADMIN_ACCOUNT_Q = Q(is_superuser=True) | Q(is_staff=True) | Q(roles__name=ROLE_ADMIN)


def has_admin_privileges(user) -> bool:
    """
    True si le compte possède des droits d'administration,
    qu'il soit actif ou suspendu (contrairement à is_supervision_admin).
    """
    return user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN)


def count_other_active_admins(excluded_user_id) -> int:
    """Nombre d'administrateurs actifs, en dehors du compte indiqué."""
    return (
        User.objects.filter(ADMIN_ACCOUNT_Q, is_active=True)
        .exclude(pk=excluded_user_id)
        .distinct()  # un admin à la fois staff ET rôle admin ne compte qu'une fois
        .count()
    )


def ensure_can_change_account_status(actor, target) -> None:
    """Règles 1 à 3 : l'auteur a-t-il le droit d'agir sur ce compte ?"""
    if not (actor.is_active and has_admin_privileges(actor)):
        raise ActorNoLongerAdmin()
    if actor.pk == target.pk:
        raise CannotChangeOwnStatus()
    if has_admin_privileges(target) and not actor.is_superuser:
        raise AdminTargetRequiresSuperAdmin()


def ensure_not_last_active_admin(target) -> None:
    """Règle 4 : la plateforme garde toujours au moins un administrateur."""
    if has_admin_privileges(target) and count_other_active_admins(target.pk) == 0:
        raise LastActiveAdmin()
