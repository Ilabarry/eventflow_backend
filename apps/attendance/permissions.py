"""
Règles d'autorisation du module Attendance.

- Fonctions utilisées par le service métier (écriture).
- Fonction et classe DRF utilisées par les vues (lecture).

Rappel de la chaîne de propriété vérifiée côté backend :
    attendance → registration → event → organizer
L'événement n'est JAMAIS fourni par le frontend : il est toujours
déduit de l'inscription chargée en base.
"""

from rest_framework.permissions import BasePermission

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


def can_view_registration_attendance(user, registration) -> bool:
    """
    Peuvent consulter la présence liée à une inscription :
        - le participant lui-même (sa propre présence) ;
        - l'organisateur de l'événement ;
        - un administrateur.
    Tout autre utilisateur est refusé (protection IDOR : connaître
    un UUID ne suffit pas pour lire les données d'autrui).
    """
    if not user or not user.is_authenticated:
        return False
    if registration.participant_id == user.id:
        return True
    return can_manage_event_attendance(user, registration.event)


class CanViewAttendance(BasePermission):
    """Permission DRF objet : obj est une Attendance."""

    message = "Vous n'avez pas accès à cette présence."

    def has_object_permission(self, request, view, obj):
        return can_view_registration_attendance(request.user, obj.registration)
