"""
Permissions DRF du module Registration.

Rappel des règles :
    - Un participant peut voir/annuler SES inscriptions.
    - Un organisateur peut voir/annuler les inscriptions de SES événements.
    - Un admin peut tout voir et tout gérer.
    - Personne d'autre ne peut rien voir (protection IDOR).
"""

from rest_framework.permissions import BasePermission

from apps.accounts.constants import ROLE_ADMIN, ROLE_ORGANIZER


def _is_admin(user) -> bool:
    """Retourne True si l'utilisateur a un rôle admin."""
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.is_staff
        or user.has_role(ROLE_ADMIN)
    )


# ==================================================================
# PERMISSION : Propriétaire de l'inscription
# ==================================================================
class IsRegistrationOwner(BasePermission):
    """
    Autorise uniquement le participant propriétaire de l'inscription
    OU un admin.
    """

    message = "Vous n'êtes pas autorisé à accéder à cette inscription."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.participant_id == request.user.id


# ==================================================================
# PERMISSION : Organisateur de l'événement
# ==================================================================
class IsEventOrganizer(BasePermission):
    """
    Autorise uniquement le propriétaire de l'événement (organisateur)
    OU un admin.

    Suppose que obj.registration.event est accessible.
    """

    message = "Vous n'êtes pas l'organisateur de cet événement."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.event.organizer_id == request.user.id


# ==================================================================
# PERMISSION : Propriétaire OU organisateur
# ==================================================================
class IsRegistrationOwnerOrEventOrganizer(BasePermission):
    """
    Autorise :
        - le participant propriétaire de l'inscription
        - l'organisateur de l'événement
        - un admin

    Utilisé pour GET /api/registrations/{id}/ et cancel.
    """

    message = "Vous n'avez pas accès à cette inscription."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        if obj.participant_id == request.user.id:
            return True
        if obj.event.organizer_id == request.user.id:
            return True
        return False


# ==================================================================
# PERMISSION : Créer une inscription (rôle participant ou organisateur)
# ==================================================================
class CanRegister(BasePermission):
    """
    Autorise tout utilisateur authentifié ET actif à s'inscrire.

    Un organisateur peut s'inscrire à l'événement d'un autre organisateur.
    Un participant peut s'inscrire à n'importe quel événement publié.
    """

    message = "Vous n'êtes pas autorisé à vous inscrire."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_active