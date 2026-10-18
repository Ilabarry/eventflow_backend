"""
Configuration de l'admin Django pour le module Tickets.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.tickets.models import Ticket, TicketType


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event",
        "price",
        "currency",
        "quantity_sold",
        "quantity_total",
        "is_active",
    )
    list_filter = ("is_active", "currency", "event")
    search_fields = ("name", "event__title")
    ordering = ("event", "price")
    readonly_fields = ("id", "quantity_sold", "created_at", "updated_at")
    autocomplete_fields = ("event",)

    fieldsets = (
        ("Identification", {"fields": ("id", "event", "name", "description")}),
        ("Prix", {"fields": ("price", "currency")}),
        ("Quantité", {"fields": ("quantity_total", "quantity_sold")}),
        ("Vente", {"fields": ("sales_start_at", "sales_end_at", "is_active")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "registration",
        "ticket_type",
        "status",
        "issued_at",
        "used_at",
    )
    list_filter = ("status", "ticket_type", "issued_at")
    search_fields = ("reference", "registration__reference", "registration__participant__email")
    ordering = ("-issued_at",)
    readonly_fields = (
        "id",
        "reference",
        "issued_at",
        "used_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("registration", "ticket_type")
    date_hierarchy = "issued_at"

    fieldsets = (
        ("Identification", {"fields": ("id", "reference", "status")}),
        ("Relations", {"fields": ("registration", "ticket_type")}),
        ("Dates", {"fields": ("issued_at", "used_at", "cancelled_at", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "registration", "registration__participant", "ticket_type"
        )