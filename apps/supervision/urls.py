"""
Routes du module Supervision.

Incluses dans eventflow_backend/urls.py sous le préfixe /api/supervision/.
"""

from django.urls import path

from apps.supervision.views import (
    AuditLogDetailView,
    AuditLogListView,
    OrganizerDetailView,
    OrganizerListView,
    UserActivateView,
    UserActivityView,
    UserDetailView,
    UserListView,
    UserSuspendView,
)

app_name = "supervision"

urlpatterns = [
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
    path("audit-logs/<uuid:pk>/", AuditLogDetailView.as_view(), name="audit-log-detail"),

    # Utilisateurs (S2)
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<uuid:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:pk>/activity/", UserActivityView.as_view(), name="user-activity"),
    path("users/<uuid:pk>/suspend/", UserSuspendView.as_view(), name="user-suspend"),
    path("users/<uuid:pk>/activate/", UserActivateView.as_view(), name="user-activate"),

    # Organisateurs (S2)
    path("organizers/", OrganizerListView.as_view(), name="organizer-list"),
    path("organizers/<uuid:pk>/", OrganizerDetailView.as_view(), name="organizer-detail"),
]
