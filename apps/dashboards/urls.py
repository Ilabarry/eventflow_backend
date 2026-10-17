"""Routes URL du module dashboards."""

from django.urls import path

from apps.dashboards.views import (
    OrganizerDashboardView,
    ParticipantDashboardView,
)


app_name = "dashboards"

urlpatterns = [
    path(
        "dashboard/organizer/",
        OrganizerDashboardView.as_view(),
        name="organizer",
    ),
    path(
        "dashboard/participant/",
        ParticipantDashboardView.as_view(),
        name="participant",
    ),
]