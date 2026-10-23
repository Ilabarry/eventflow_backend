"""
Services métier du module Notifications d'EVENTFLOW.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.notifications.constants import NotificationType
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Regroupe les opérations métier sur les notifications."""

    # ------------------------------------------------------------------
    # CRÉATION
    # ------------------------------------------------------------------
    @staticmethod
    def create_notification(
        *,
        user,
        title: str,
        message: str,
        notification_type: str = NotificationType.SYSTEM,
        related_entity_type: str = "",
        related_entity_id: str = "",
        metadata: dict | None = None,
    ) -> Notification:
        """
        Crée une notification pour un utilisateur donné.

        Le paramètre user doit provenir du contexte fiable de l'application
        (ex: request.user), JAMAIS d'un identifiant fourni par le client.
        """
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            type=notification_type,
            related_entity_type=related_entity_type,
            related_entity_id=str(related_entity_id) if related_entity_id else "",
            metadata=metadata or {},
        )
        logger.info(
            "Notification created | user=%s | type=%s | id=%s",
            user.id, notification_type, notification.id,
        )
        return notification

    @staticmethod
    @transaction.atomic
    def notify_users(
        *,
        users,
        title: str,
        message: str,
        notification_type: str = NotificationType.SYSTEM,
        related_entity_type: str = "",
        related_entity_id: str = "",
        metadata: dict | None = None,
    ) -> int:
        """
        Crée une notification pour plusieurs utilisateurs (bulk).

        Utilise bulk_create() pour éviter N requêtes SQL.
        Attention : bulk_create ne déclenche pas les signaux Django.

        Args:
            users: QuerySet ou liste d'utilisateurs.
            (autres args identiques à create_notification)

        Returns:
            Le nombre de notifications créées.
        """
        now = timezone.now()
        notifications = [
            Notification(
                user=user,
                title=title,
                message=message,
                type=notification_type,
                related_entity_type=related_entity_type,
                related_entity_id=str(related_entity_id) if related_entity_id else "",
                metadata=metadata or {},
                created_at=now,
            )
            for user in users
        ]
        if not notifications:
            logger.warning("notify_users called with empty user list")
            return 0

        created = Notification.objects.bulk_create(notifications, batch_size=500)
        logger.info(
            "Bulk notifications created | count=%s | type=%s",
            len(created), notification_type,
        )
        return len(created)

    @staticmethod
    def notify_queryset(
        *,
        queryset,
        title: str,
        message: str,
        notification_type: str = NotificationType.SYSTEM,
        related_entity_type: str = "",
        related_entity_id: str = "",
        metadata: dict | None = None,
    ) -> int:
        """
        Crée une notification pour tous les utilisateurs d'un QuerySet.

        Exemple : notifier tous les participants confirmés d'un événement.
        """
        return NotificationService.notify_users(
            users=queryset,
            title=title,
            message=message,
            notification_type=notification_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # LECTURE / MARQUAGE
    # ------------------------------------------------------------------
    @staticmethod
    def mark_as_read(notification: Notification) -> Notification:
        """Marque une notification comme lue (idempotent)."""
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
            logger.info("Notification marked as read | id=%s", notification.id)
        return notification

    @staticmethod
    def mark_all_as_read(*, user) -> int:
        """Marque toutes les notifications non lues d'un utilisateur."""
        count = Notification.objects.filter(
            user=user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )
        logger.info("All notifications marked as read | user=%s | count=%s", user.id, count)
        return count