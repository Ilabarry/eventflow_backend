"""
Configuration de l'admin Django pour le module Payment.
"""

from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_reference",
        "registration",
        "amount",
        "currency",
        "payment_method",
        "provider",
        "status",
        "created_at",
    )
    list_filter = ("status", "payment_method", "provider", "currency", "created_at")
    search_fields = (
        "transaction_reference",
        "provider_reference",
        "registration__reference",
        "registration__participant__email",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "transaction_reference",
        "provider_reference",
        "paid_at",
        "cancelled_at",
        "refunded_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("registration",)
    date_hierarchy = "created_at"

    fieldsets = (
        ("Identification", {"fields": ("id", "transaction_reference", "status")}),
        ("Relations", {"fields": ("registration",)}),
        ("Montant", {"fields": ("amount", "currency")}),
        ("Méthode et provider", {"fields": ("payment_method", "provider", "provider_reference")}),
        ("Échec", {"fields": ("failure_code", "failure_message")}),
        ("Idempotence", {"fields": ("idempotency_key",)}),
        ("Métadonnées", {"fields": ("metadata",)}),
        ("Dates", {"fields": ("paid_at", "cancelled_at", "refunded_at", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("registration", "registration__participant", "registration__event")