
"""Configuration de l'administration Django pour Notifications."""

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Affichage et recherche des notifications dans Django Admin."""

    list_display = (
        "title",
        "user",
        "type",
        "is_read",
        "created_at",
    )

    list_filter = (
        "type",
        "is_read",
        "created_at",
    )

    search_fields = (
        "title",
        "message",
        "user__email",
    )

    readonly_fields = (
        "id",
        "created_at",
    )

    list_select_related = ("user",)
    ordering = ("-created_at",)
    list_per_page = 25
