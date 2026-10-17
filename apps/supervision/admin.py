"""
Admin Django du module Supervision : journal d'audit en LECTURE SEULE.

Même un super-utilisateur ne peut ni ajouter, ni modifier, ni supprimer
une entrée depuis /admin/ (le modèle le refuse aussi au niveau du code).
"""

from django.contrib import admin

from apps.supervision.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_email", "action", "entity_type", "entity_id", "result", "ip_address")
    list_filter = ("action", "entity_type", "result", "created_at")
    search_fields = ("actor_email", "entity_id", "description", "reason")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("actor",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
