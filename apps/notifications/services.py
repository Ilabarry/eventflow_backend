
"""
Services métier du module Notifications d'EVENTFLOW.

Les vues appelleront ces méthodes pour créer des notifications
et gérer leur état de lecture.
"""

from django.utils import timezone

from .models import Notification


class NotificationService:
    """Regroupe les opérations métier sur les notifications."""

    @staticmethod
    def create_notification(
        *,
        user,
        title,
        message,
        notification_type=Notification.Type.SYSTEM,
        related_entity_type="",
        related_entity_id="",
        metadata=None,
    ):
        """
        Crée une notification pour un utilisateur donné.

        Le paramètre user doit provenir du contexte fiable de l'application,
        et non d'un identifiant librement fourni par le client Angular.
        """

        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            type=notification_type,
            related_entity_type=related_entity_type,
            related_entity_id=str(related_entity_id) if related_entity_id else "",
            metadata=metadata or {},
        )

    @staticmethod
    def mark_as_read(notification):
        """Marque une notification comme lue."""

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()

            notification.save(
                update_fields=["is_read", "read_at"]
            )

        return notification

    @staticmethod
    def mark_all_as_read(*, user):
        """Marque toutes les notifications non lues d'un utilisateur."""

        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )
