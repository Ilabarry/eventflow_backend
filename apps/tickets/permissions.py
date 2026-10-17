"""
Permissions DRF du module Tickets.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.constants import ROLE_ADMIN


def _is_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN)


class IsTicketOwner(BasePermission):
    """Seul le participant propriétaire ou un admin."""
    message = "Vous n'êtes pas autorisé à accéder à ce ticket."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.registration.participant_id == request.user.id


class IsTicketOwnerOrEventOrganizer(BasePermission):
    """Participant, organisateur de l'événement, ou admin."""

    message = "Vous n'avez pas accès à ce ticket."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        if obj.registration.participant_id == request.user.id:
            return True
        if obj.registration.event.organizer_id == request.user.id:
            return True
        return False


class IsTicketTypeOwner(BasePermission):
    """Seul l'organisateur de l'événement ou un admin."""
    message = "Vous n'êtes pas l'organisateur de cet événement."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.event.organizer_id == request.user.id


class IsAdminOnly(BasePermission):
    message = "Action réservée aux administrateurs."

    def has_permission(self, request, view):
        return _is_admin(request.user)