"""Routes URL du module dashboards."""

from django.urls import path

from apps.dashboards.views import (
    AdminDashboardView,
    AdminStatisticsView,
    OrganizerDashboardView,
    OrganizerStatisticsView,
    ParticipantDashboardView,
)

app_name = "dashboards"

urlpatterns = [
    path("dashboard/organizer/", OrganizerDashboardView.as_view(), name="organizer"),
    path("dashboard/participant/", ParticipantDashboardView.as_view(), name="participant"),
    path("dashboard/admin/", AdminDashboardView.as_view(), name="admin"),
    path("dashboard/organizer/statistics/", OrganizerStatisticsView.as_view(), name="organizer-statistics"),
    path("dashboard/admin/statistics/", AdminStatisticsView.as_view(), name="admin-statistics"),
]