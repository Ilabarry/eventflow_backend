"""
Permissions DRF du module Notifications.

Un utilisateur ne peut accéder qu'à SES propres notifications.
"""

from rest_framework.permissions import BasePermission


class IsNotificationOwner(BasePermission):
    """
    Autorise uniquement le propriétaire de la notification.

    Suppose que la vue a bien récupéré l'objet (get_object).
    """

    message = "Vous n'avez pas accès à cette notification."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id