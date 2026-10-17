"""
Configuration de l'admin Django pour le module Attendance.

L'admin est volontairement en LECTURE SEULE :
    - les check-ins doivent passer par le service métier (vérifications
      d'inscription, d'événement, de doublon, de traçabilité) ;
    - créer ou modifier une présence à la main dans l'admin
      contournerait toutes ces règles.
Une correction administrative tracée pourra être ajoutée plus tard,
via une action dédiée qui appellera le service.
"""

from django.contrib import admin

from apps.attendance.models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "registration_reference",
        "participant",
        "event",
        "status",
        "checked_in_at",
        "check_in_method",
        "recorded_by",
    )
    list_filter = ("status", "check_in_method", "checked_in_at")
    search_fields = (
        "registration__reference",
        "registration__participant__email",
        "registration__participant__first_name",
        "registration__participant__last_name",
        "registration__event__title",
    )
    ordering = ("-created_at",)
    date_hierarchy = "checked_in_at"
    # Charge inscription, participant, événement et auteur en une seule
    # requête SQL, au lieu d'une requête par ligne affichée (N+1).
    list_select_related = (
        "registration",
        "registration__participant",
        "registration__event",
        "recorded_by",
    )

    fieldsets = (
        ("Identification", {"fields": ("id", "registration", "status")}),
        ("Check-in", {"fields": ("checked_in_at", "check_in_method", "recorded_by")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )

    # ------------------------------------------------------------------
    # Colonnes calculées (lues depuis Registration, pas dupliquées)
    # ------------------------------------------------------------------
    @admin.display(description="Référence", ordering="registration__reference")
    def registration_reference(self, obj):
        return obj.registration.reference

    @admin.display(description="Participant", ordering="registration__participant__email")
    def participant(self, obj):
        return obj.registration.participant

    @admin.display(description="Événement", ordering="registration__event__title")
    def event(self, obj):
        return obj.registration.event

    # ------------------------------------------------------------------
    # Lecture seule
    # ------------------------------------------------------------------
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
