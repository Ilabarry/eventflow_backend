
"""
Vues API du module Notifications d'EVENTFLOW.

Toutes les opérations de consultation et de modification
sont limitées aux notifications de l'utilisateur authentifié.
"""

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.pagination.standard import StandardPagination
from common.responses.standard import APIResponse

from .models import Notification
from .serializers import NotificationSerializer
from .selectors import NotificationSelector
from .services import NotificationService
from apps.notifications.constants import NotificationType
from .constants import NotificationType


class NotificationListView(GenericAPIView):
    """Liste paginée des notifications de l'utilisateur connecté."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = StandardPagination

    def get(self, request, *args, **kwargs):
        raw_is_read = request.query_params.get("is_read")
        is_read = None

        if raw_is_read is not None:
            value = raw_is_read.strip().lower()

            if value not in ("true", "false"):
                return APIResponse.error(
                    message="La valeur de is_read doit être true ou false.",
                    errors={
                        "is_read": ["Valeurs acceptées : true, false."]
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            is_read = value == "true"

        notification_type = request.query_params.get("type")

        if notification_type and notification_type not in NotificationType.values:
            return APIResponse.error(
                message="Le type de notification est invalide.",
                errors={
                    "type": ["Choisissez un type de notification valide."]
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        queryset = NotificationSelector.list_for_user(
            user=request.user,
            is_read=is_read,
            notification_type=notification_type or None,
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        # Conserve la pagination commune et enveloppe son résultat
        # dans le format de réponse standard d'EVENTFLOW.
        paginated_response = self.get_paginated_response(serializer.data)

        return APIResponse.success(
            data=paginated_response.data,
            message="Notifications récupérées avec succès.",
        )


class NotificationUnreadCountView(APIView):
    """Retourne le nombre de notifications non lues."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = NotificationSelector.unread_count(user=request.user)

        return APIResponse.success(
            data={"unread_count": count},
            message="Nombre de notifications non lues récupéré.",
        )



class NotificationDetailView(APIView):
    """Consulte ou supprime une notification de l'utilisateur connecté."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        notification = NotificationSelector.get_for_user(
            user=request.user,
            notification_id=pk,
        )

        if notification is None:
            return APIResponse.error(
                message="Notification introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = NotificationSerializer(notification)

        return APIResponse.success(
            data=serializer.data,
            message="Notification récupérée avec succès.",
        )

    def delete(self, request, pk):
        notification = NotificationSelector.get_for_user(
            user=request.user,
            notification_id=pk,
        )

        if notification is None:
            return APIResponse.error(
                message="Notification introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        notification.delete()

        return APIResponse.success(
            message="Notification supprimée avec succès.",
        )


class NotificationMarkReadView(APIView):
    """Marque une notification appartenant à l'utilisateur comme lue."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = NotificationSelector.get_for_user(
            user=request.user,
            notification_id=pk,
        )

        if notification is None:
            return APIResponse.error(
                message="Notification introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        notification = NotificationService.mark_as_read(notification)
        serializer = NotificationSerializer(notification)

        return APIResponse.success(
            data=serializer.data,
            message="Notification marquée comme lue.",
        )


class NotificationMarkAllReadView(APIView):
    """Marque toutes les notifications non lues comme lues."""

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        updated_count = NotificationService.mark_all_as_read(
            user=request.user,
        )

        return APIResponse.success(
            data={"updated_count": updated_count},
            message="Notifications non lues marquées comme lues.",
        )

