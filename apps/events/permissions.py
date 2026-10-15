"""
Permissions DRF spécifiques au module Event.

Rappel :
    - has_permission() : vérifie l'accès à la vue (avant chargement de l'objet)
    - has_object_permission() : vérifie l'accès à un objet précis

Ici, on combine :
    - Permissions globales (IsAuthenticated, HasPermission)
    - Ownership (l'utilisateur est-il propriétaire de l'événement ?)
    - Rôle (admin vs organisateur)
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.constants import ROLE_ADMIN, ROLE_ORGANIZER


# ==================================================================
# PERMISSION : Propriétaire de l'événement
# ==================================================================
class IsEventOwner(BasePermission):
    """
    Autorise uniquement le propriétaire de l'événement.

    Suppose que la vue a bien récupéré l'objet (get_object).
    """

    message = "Vous n'êtes pas le propriétaire de cet événement."

    def has_object_permission(self, request, view, obj):
        return obj.organizer_id == request.user.id


class IsEventOwnerOrAdmin(BasePermission):
    """
    Autorise le propriétaire OU un administrateur.

    Utilisé pour les opérations sensibles :
        - Modification d'un événement
        - Suppression
        - Publication
        - Annulation
    """

    message = "Seul le propriétaire ou un administrateur peut effectuer cette action."

    def has_object_permission(self, request, view, obj):
        # Superuser Django
        if request.user.is_superuser or request.user.is_staff:
            return True

        # Rôle administrateur
        if request.user.has_role(ROLE_ADMIN):
            return True

        # Propriétaire de l'événement
        if obj.organizer_id == request.user.id:
            return True

        return False


# ==================================================================
# PERMISSION : Peut voir les événements non publiés
# ==================================================================
class CanViewUnpublishedEvent(BasePermission):
    """
    Autorise la consultation d'un événement non publié
    (DRAFT, CANCELLED, COMPLETED) uniquement au propriétaire
    ou à un administrateur.
    """

    message = "Cet événement n'est pas public."

    def has_object_permission(self, request, view, obj):
        # Les événements publiés sont visibles par tous
        if obj.status == "PUBLISHED":
            return True

        # Sinon, vérifier les droits
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        if request.user.has_role(ROLE_ADMIN):
            return True

        if obj.organizer_id == request.user.id:
            return True

        return False