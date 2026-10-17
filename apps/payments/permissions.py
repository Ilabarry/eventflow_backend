"""
Permissions DRF du module Payment.

Règles :
    - Participant : peut voir/annuler SES paiements.
    - Organisateur : peut voir les paiements de SES événements.
    - Admin : peut tout faire (y compris rembourser).
"""

from rest_framework.permissions import BasePermission

from apps.accounts.constants import ROLE_ADMIN, ROLE_ORGANIZER


def _is_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN)


class IsPaymentOwner(BasePermission):
    """Seul le participant propriétaire ou un admin."""

    message = "Vous n'êtes pas autorisé à accéder à ce paiement."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.registration.participant_id == request.user.id


class IsPaymentOwnerOrEventOrganizer(BasePermission):
    """
    Autorise :
        - le participant propriétaire
        - l'organisateur de l'événement
        - un admin
    """

    message = "Vous n'avez pas accès à ce paiement."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        if obj.registration.participant_id == request.user.id:
            return True
        if obj.registration.event.organizer_id == request.user.id:
            return True
        return False


class IsAdminOnly(BasePermission):
    """Réservé aux admins (remboursement, etc.)."""

    message = "Cette action est réservée aux administrateurs."

    def has_permission(self, request, view):
        return _is_admin(request.user)