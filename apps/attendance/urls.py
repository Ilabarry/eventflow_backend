"""
Routes URL du module Attendance.

Incluses dans eventflow_backend/urls.py sous le préfixe /api/.
"""

from django.urls import path

from apps.attendance.views import (
    AttendanceDetailView,
    CheckInView,
    EventAttendanceListView,
    EventAttendanceStatsView,
    MarkAbsentView,
    MyAttendanceView,
    RegistrationAttendanceView,
    QRCheckInView,
)

app_name = "attendance"

urlpatterns = [
    # Organisateur
    path("attendance/check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("attendance/mark-absent/", MarkAbsentView.as_view(), name="attendance-mark-absent"),
    path("attendance/check-in/qr/", QRCheckInView.as_view(), name="attendance-check-in-qr"),

    path(
        "events/<uuid:event_id>/attendance/",
        EventAttendanceListView.as_view(),
        name="event-attendance-list",
    ),
    path(
        "events/<uuid:event_id>/attendance/stats/",
        EventAttendanceStatsView.as_view(),
        name="event-attendance-stats",
    ),

    # Participant
    path("attendance/me/", MyAttendanceView.as_view(), name="attendance-me"),

    # Consultation
    path("attendance/<uuid:pk>/", AttendanceDetailView.as_view(), name="attendance-detail"),
    path(
        "registrations/<uuid:registration_id>/attendance/",
        RegistrationAttendanceView.as_view(),
        name="registration-attendance",
    ),
]
