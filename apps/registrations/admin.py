"""
Configuration de l'admin Django pour le module Registration.
"""

from django.contrib import admin

from apps.registrations.models import Registration


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "participant",
        "event",
        "status",
        "registered_at",
        "cancelled_at",
    )
    list_filter = ("status", "registered_at", "cancelled_at")
    search_fields = (
        "reference",
        "participant__email",
        "participant__first_name",
        "participant__last_name",
        "event__title",
    )
    ordering = ("-registered_at",)
    readonly_fields = (
        "id",
        "reference",
        "registered_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("participant", "event")
    date_hierarchy = "registered_at"

    fieldsets = (
        ("Identification", {"fields": ("id", "reference", "status")}),
        ("Relations", {"fields": ("participant", "event")}),
        ("Dates", {"fields": ("registered_at", "cancelled_at", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        """Optimise la requête admin avec select_related."""
        return super().get_queryset(request).select_related("participant", "event")