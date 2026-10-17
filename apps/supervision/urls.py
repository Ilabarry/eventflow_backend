"""
Routes du module Supervision.

Incluses dans eventflow_backend/urls.py sous le préfixe /api/supervision/.
"""

from django.urls import path

from apps.supervision.views import AuditLogDetailView, AuditLogListView

app_name = "supervision"

urlpatterns = [
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
    path("audit-logs/<uuid:pk>/", AuditLogDetailView.as_view(), name="audit-log-detail"),
]
