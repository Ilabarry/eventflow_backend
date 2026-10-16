"""
Routes URL du module Attendance.

Incluses dans eventflow_backend/urls.py sous le préfixe /api/.
"""

from django.urls import path

from apps.attendance.views import (
    AttendanceDetailView,
    CheckInView,
    MarkAbsentView,
    MyAttendanceView,
    RegistrationAttendanceView,
)

app_name = "attendance"

urlpatterns = [
    # Organisateur
    path("attendance/check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("attendance/mark-absent/", MarkAbsentView.as_view(), name="attendance-mark-absent"),

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
