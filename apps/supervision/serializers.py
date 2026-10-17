"""
Serializers du module Supervision.

Phase S1 : journal d'audit (lecture seule).
"""

from rest_framework import serializers

from apps.supervision.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Entrée du journal d'audit.

    L'adresse IP et le navigateur sont des données personnelles : ils ne
    sont exposés QUE dans cette API, réservée aux administrateurs.
    """

    actor_id = serializers.UUIDField(source="actor.id", read_only=True, allow_null=True, default=None)
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    entity_type_label = serializers.CharField(source="get_entity_type_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "created_at",
            "actor_id",
            "actor_email",
            "action",
            "action_label",
            "entity_type",
            "entity_type_label",
            "entity_id",
            "description",
            "reason",
            "result",
            "metadata",
            "ip_address",
            "user_agent",
        )
        read_only_fields = fields
