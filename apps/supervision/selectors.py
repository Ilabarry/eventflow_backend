"""
Selectors du module Supervision : lectures en base.

Phase S1 : journal d'audit.
"""

from django.db.models import QuerySet

from apps.supervision.models import AuditLog


def get_audit_logs() -> QuerySet[AuditLog]:
    """Toutes les entrées, les plus récentes d'abord, acteur préchargé."""
    return AuditLog.objects.select_related("actor").order_by("-created_at")


def get_audit_log_by_id(audit_log_id) -> AuditLog | None:
    return AuditLog.objects.select_related("actor").filter(id=audit_log_id).first()
