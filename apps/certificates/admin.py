from django.contrib import admin

# Register your models here.
"""
Configuration de l'admin Django pour le module Certificates.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.certificates.models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "participant_name",
        "event_title",
        "status",
        "issued_at",
        "has_pdf",
    )
    list_filter = ("status", "issued_at")
    search_fields = (
        "reference",
        "verification_code",
        "registration__reference",
        "registration__participant__email",
    )
    ordering = ("-issued_at",)
    readonly_fields = (
        "id",
        "reference",
        "verification_code",
        "issued_at",
        "revoked_at",
        "created_at",
        "updated_at",
        "pdf_preview",
    )
    autocomplete_fields = ("registration", "revoked_by")
    date_hierarchy = "issued_at"

    fieldsets = (
        ("Identification", {"fields": ("id", "reference", "verification_code", "status")}),
        ("Relation", {"fields": ("registration",)}),
        ("PDF", {"fields": ("pdf_file", "pdf_preview")}),
        ("Révocation", {"fields": ("revoked_at", "revoked_by")}),
        ("Dates", {"fields": ("issued_at", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "registration", "registration__participant", "registration__event"
        )

    @admin.display(description="Participant")
    def participant_name(self, obj):
        return obj.registration.participant.full_name

    @admin.display(description="Événement")
    def event_title(self, obj):
        return obj.registration.event.title

    @admin.display(description="PDF ?", boolean=True)
    def has_pdf(self, obj):
        return bool(obj.pdf_file)

    @admin.display(description="Aperçu")
    def pdf_preview(self, obj):
        if obj.pdf_file:
            return format_html(
                '<a href="{}" target="_blank">Télécharger le PDF</a>',
                obj.pdf_file.url,
            )
        return "—"

    def has_add_permission(self, request):
        # Un certificat doit être créé via le service métier (vérifications)
        return False