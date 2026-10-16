"""
Règles d'autorisation du module Attendance.

Phase 2 : fonctions utilisées par le service métier.
Phase 3 : les classes de permission DRF (pour les vues) seront ajoutées ici.

Rappel de la chaîne de propriété vérifiée côté backend :
    attendance → registration → event → organizer
L'événement n'est JAMAIS fourni par le frontend : il est toujours
déduit de l'inscription chargée en base.
"""

from apps.accounts.constants import ROLE_ADMIN


def is_platform_admin(user) -> bool:
    """
    Retourne True si l'utilisateur est administrateur de la plateforme.

    Même définition que dans apps/registrations/permissions.py,
    pour un comportement identique dans tous les modules.
    """
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN)


def can_manage_event_attendance(user, event) -> bool:
    """
    Un utilisateur peut gérer les présences d'un événement s'il en est
    l'organisateur (propriétaire) ou s'il est administrateur.
    """
    if not user or not user.is_authenticated:
        return False
    return is_platform_admin(user) or event.organizer_id == user.id
