"""
Configuration de l'admin Django pour le module Event.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.events.models import Category, Event


# ==================================================================
# ADMIN : Category
# ==================================================================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "events_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)
    readonly_fields = ("id", "slug", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        (None, {"fields": ("id", "name", "slug", "description", "icon")}),
        ("Statut", {"fields": ("is_active",)}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )

    def events_count(self, obj):
        """Affiche le nombre d'événements utilisant cette catégorie."""
        return obj.events.count()
    events_count.short_description = "Événements"


# ==================================================================
# ADMIN : Event
# ==================================================================
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organizer",
        "category",
        "format",
        "status",
        "start_at",
        "created_at",
    )
    list_filter = (
        "status",
        "format",
        "participation_type",
        "capacity_type",
        "category",
        "created_at",
    )
    search_fields = ("title", "short_description", "description", "city")
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "published_at",
        "cover_preview",
    )
    autocomplete_fields = ("organizer", "category")
    date_hierarchy = "start_at"

    fieldsets = (
        ("Identification", {"fields": ("id", "organizer", "category", "status", "published_at")}),
        ("Contenu", {"fields": ("title", "short_description", "description", "cover_image", "cover_preview")}),
        ("Format et participation", {"fields": ("format", "participation_type")}),
        ("Dates", {"fields": ("start_at", "end_at")}),
        ("Lieu (présentiel)", {"fields": ("venue_name", "address", "city", "room")}),
        ("Accès en ligne", {"fields": ("online_platform", "access_url")}),
        ("Capacité", {"fields": ("capacity_type", "capacity_limit")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def cover_preview(self, obj):
        """Affiche un aperçu de l'image de couverture."""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 300px;" />',
                obj.cover_image.url,
            )
        return "—"
    cover_preview.short_description = "Aperçu"