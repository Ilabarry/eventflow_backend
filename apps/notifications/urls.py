
"""
Routes API du module Notifications d'EVENTFLOW.
"""

from django.urls import path

from .views import (
    NotificationListView,
    NotificationUnreadCountView,
    NotificationDetailView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
)

app_name = "notifications"

urlpatterns = [
    # Liste paginée des notifications de l'utilisateur connecté.
    path(
        "",
        NotificationListView.as_view(),
        name="list",
    ),

    # Nombre de notifications non lues.
    path(
        "unread-count/",
        NotificationUnreadCountView.as_view(),
        name="unread-count",
    ),

    # Marquer toutes les notifications comme lues.
    path(
        "read-all/",
        NotificationMarkAllReadView.as_view(),
        name="read-all",
    ),

    # Marquer une notification comme lue.
    path(
        "<uuid:pk>/read/",
        NotificationMarkReadView.as_view(),
        name="mark-read",
    ),

    # Consulter ou supprimer une notification précise.
    path(
        "<uuid:pk>/",
        NotificationDetailView.as_view(),
        name="detail",
    ),
]
