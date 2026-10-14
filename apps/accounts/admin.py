"""
Configuration de l'admin Django pour l'application 'accounts'.

Permet aux administrateurs de gérer les utilisateurs, rôles et
permissions depuis l'interface /admin/.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Permission, Role, User


# ==================================================================
# ADMIN : Permission
# ==================================================================
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "name", "created_at")
    search_fields = ("codename", "name")
    ordering = ("codename",)
    readonly_fields = ("id", "created_at")


# ==================================================================
# ADMIN : Role
# ==================================================================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    search_fields = ("name",)
    filter_horizontal = ("permissions",)
    readonly_fields = ("id", "created_at")


# ==================================================================
# ADMIN : User
# ==================================================================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin personnalisé pour notre User (basé sur email, pas username).

    On redéfinit les fieldsets car AbstractUser en fournit par défaut
    qui référencent 'username' (qu'on a supprimé).
    """

    # Colonnes affichées dans la liste
    list_display = ("email", "first_name", "last_name", "phone", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser", "roles")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at", "last_login", "date_joined")

    # Formulaire d'édition
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        (_("Informations personnelles"), {
            "fields": ("first_name", "last_name", "phone", "profile_picture")
        }),
        (_("Rôles"), {"fields": ("roles",)}),
        (_("Permissions Django"), {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        (_("Dates importantes"), {
            "fields": ("last_login", "date_joined", "created_at", "updated_at")
        }),
    )

    # Formulaire de création
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone", "password1", "password2"),
        }),
    )
    filter_horizontal = ("roles", "groups", "user_permissions")
