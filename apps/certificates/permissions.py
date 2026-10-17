"""
Permissions DRF du module Certificates.

Règles :
    - Participant : peut voir/télécharger SES certificats.
    - Organisateur : peut voir les certificats de SES événements.
    - Admin : peut tout voir.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.constants import ROLE_ADMIN


def _is_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN)


class IsCertificateOwner(BasePermission):
    """Participant propriétaire ou admin."""
    message = "Vous n'êtes pas autorisé à accéder à ce certificat."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.registration.participant_id == request.user.id


class IsCertificateOwnerOrOrganizer(BasePermission):
    """Participant, organisateur de l'événement, ou admin."""

    message = "Vous n'avez pas accès à ce certificat."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        if obj.registration.participant_id == request.user.id:
            return True
        if obj.registration.event.organizer_id == request.user.id:
            return True
        return False


class IsEventOrganizerOrAdmin(BasePermission):
    """Organisateur propriétaire ou admin (pour générer/révoquer)."""

    message = "Vous n'êtes pas l'organisateur de cet événement."

    def has_object_permission(self, request, view, obj):
        if _is_admin(request.user):
            return True
        return obj.registration.event.organizer_id == request.user.id


class IsAdminOnly(BasePermission):
    message = "Action réservée aux administrateurs."

    def has_permission(self, request, view):
        return _is_admin(request.user)