
"""
Sélecteurs de données du module Notifications d'EVENTFLOW.

Les sélecteurs centralisent les requêtes de lecture en base.
Chaque méthode de consultation est limitée à un utilisateur.
"""

from .models import Notification


class NotificationSelector:
    """Regroupe les requêtes de consultation des notifications."""

    @staticmethod
    def list_for_user(*, user, is_read=None, notification_type=None):
        """
        Retourne les notifications d'un utilisateur.

        Les filtres de lecture et de type sont facultatifs.
        L'ordre par défaut est défini dans le modèle Notification.
        """

        queryset = Notification.objects.filter(user=user)

        if is_read is not None:
            queryset = queryset.filter(is_read=is_read)

        if notification_type:
            queryset = queryset.filter(type=notification_type)

        return queryset

    @staticmethod
    def unread_count(*, user):
        """Compte les notifications non lues d'un utilisateur."""

        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).count()

    @staticmethod
    def get_for_user(*, user, notification_id):
        """
        Recherche une notification appartenant à l'utilisateur.

        Retourne None si la notification n'existe pas
        ou n'appartient pas à cet utilisateur.
        """

        return Notification.objects.filter(
            user=user,
            pk=notification_id,
        ).first()
