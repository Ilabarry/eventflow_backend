
"""
Serializers du module Notifications d'EVENTFLOW.

Ce serializer définit les données exposées à Angular.
La création et la modification des notifications seront
contrôlées par les services et les vues de l'API.
"""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Convertit une notification en données JSON."""

    class Meta:
        model = Notification

        fields = [
            "id",
            "title",
            "message",
            "type",
            "is_read",
            "read_at",
            "related_entity_type",
            "related_entity_id",
            "metadata",
            "created_at",
        ]

        # L'API ne doit pas laisser le client modifier directement
        # les champs de la notification à travers ce serializer.
        # Les actions de lecture seront gérées par des endpoints dédiés.
        read_only_fields = fields
