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
    SupervisionAttendanceListView,
    SupervisionCategoryActivateView,
    SupervisionCategoryDeactivateView,
    SupervisionCategoryDetailView,
    SupervisionCategoryListView,
    SupervisionEventCancelView,
    SupervisionEventDetailView,
    SupervisionEventListView,
    SupervisionRegistrationDetailView,
    SupervisionRegistrationListView,
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

    # Événements (S3) : consultation et annulation uniquement
    path("events/", SupervisionEventListView.as_view(), name="event-list"),
    path("events/<uuid:pk>/", SupervisionEventDetailView.as_view(), name="event-detail"),
    path("events/<uuid:pk>/cancel/", SupervisionEventCancelView.as_view(), name="event-cancel"),

    # Catégories (S3)
    path("categories/", SupervisionCategoryListView.as_view(), name="category-list"),
    path("categories/<uuid:pk>/", SupervisionCategoryDetailView.as_view(), name="category-detail"),
    path(
        "categories/<uuid:pk>/deactivate/",
        SupervisionCategoryDeactivateView.as_view(),
        name="category-deactivate",
    ),
    path(
        "categories/<uuid:pk>/activate/",
        SupervisionCategoryActivateView.as_view(),
        name="category-activate",
    ),

    # Inscriptions et présences (S4) : lecture seule
    path("registrations/", SupervisionRegistrationListView.as_view(), name="registration-list"),
    path(
        "registrations/<uuid:pk>/",
        SupervisionRegistrationDetailView.as_view(),
        name="registration-detail",
    ),
    path("attendance/", SupervisionAttendanceListView.as_view(), name="attendance-list"),
]
