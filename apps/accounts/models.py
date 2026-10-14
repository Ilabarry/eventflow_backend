from django.db import models

"""
Modèles de l'application 'accounts' pour EVENTFLOW.

Contient :
    - Permission : action granulaire (ex: event.create)
    - Role : regroupement de permissions (Participant, Organisateur, Admin)
    - User : utilisateur personnalisé basé sur l'email
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager


# ==================================================================
# MODÈLE : Permission
# ==================================================================
class Permission(models.Model):
    """
    Représente une permission granulaire (action autorisée).

    Exemples :
        - event.create
        - event.update
        - registration.cancel
        - user.suspend

    Le champ 'codename' est unique : il sert d'identifiant technique
    utilisé dans le code (ex: @has_permission('event.create')).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nom",
        help_text="Nom lisible (ex: 'Créer un événement').",
    )
    codename = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Code technique",
        help_text="Code unique (ex: 'event.create').",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Description détaillée de la permission.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ["codename"]

    def __str__(self):
        return self.codename


# ==================================================================
# MODÈLE : Role
# ==================================================================
class Role(models.Model):
    """
    Regroupe un ensemble de permissions.

    Trois rôles principaux pour EVENTFLOW :
        - Participant : s'inscrit aux événements
        - Organisateur : crée et gère ses événements
        - Administrateur : supervise la plateforme

    Le champ 'name' est unique. On utilise les constantes de
    apps.accounts.constants pour éviter les fautes de frappe.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nom du rôle",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
        verbose_name="Permissions",
        help_text="Permissions accordées par ce rôle.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"
        ordering = ["name"]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Méthodes métier
    # ------------------------------------------------------------------
    def assign_permission(self, permission):
        """Ajoute une permission à ce rôle (idempotent)."""
        self.permissions.add(permission)

    def remove_permission(self, permission):
        """Retire une permission de ce rôle."""
        self.permissions.remove(permission)

    def has_permission(self, codename: str) -> bool:
        """Vérifie si ce rôle possède la permission donnée."""
        return self.permissions.filter(codename=codename).exists()


# ==================================================================
# MODÈLE : User
# ==================================================================
class User(AbstractUser):

    # ------------------------------------------------------------------
    # Suppression du champ username
    # ------------------------------------------------------------------
    username = None

    # ------------------------------------------------------------------
    # Identifiant principal
    # ------------------------------------------------------------------
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    email = models.EmailField(
        unique=True,
        verbose_name="Adresse email",
        error_messages={
            "unique": _("Un compte avec cet email existe déjà."),
        },
    )

    # ------------------------------------------------------------------
    # Informations personnelles
    # ------------------------------------------------------------------
    first_name = models.CharField(
        max_length=150,
        verbose_name="Prénom",
    )
    last_name = models.CharField(
        max_length=150,
        verbose_name="Nom",
    )
    phone = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Téléphone",
        help_text="Numéro au format international (ex: +221771234567).",
        error_messages={
            "unique": _("Un compte avec ce numéro de téléphone existe déjà."),
        },
    )
    profile_picture = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        verbose_name="Photo de profil",
    )

    # ------------------------------------------------------------------
    # Rôles (M2M)
    # ------------------------------------------------------------------
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="users",
        verbose_name="Rôles",
        help_text="Rôles attribués à cet utilisateur.",
    )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour",
    )

    # ------------------------------------------------------------------
    # Configuration Django
    # ------------------------------------------------------------------
    USERNAME_FIELD = "email"  # Champ utilisé pour se connecter
    REQUIRED_FIELDS = ["first_name", "last_name", "phone"]  # Pour createsuperuser

    objects = UserManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------
    @property
    def full_name(self) -> str:
        """Retourne le nom complet."""
        return f"{self.first_name} {self.last_name}".strip()

    # ------------------------------------------------------------------
    # Gestion des rôles
    # ------------------------------------------------------------------
    def add_role(self, role_name: str):
        """Ajoute un rôle par son nom (ex: 'participant')."""
        role, _ = Role.objects.get_or_create(name=role_name)
        self.roles.add(role)

    def remove_role(self, role_name: str):
        """Retire un rôle par son nom."""
        self.roles.filter(name=role_name).delete()

    def has_role(self, role_name: str) -> bool:
        """Vérifie si l'utilisateur possède un rôle donné."""
        return self.roles.filter(name=role_name).exists()

    def has_permission(self, codename: str) -> bool:
        """
        Vérifie si l'utilisateur possède une permission donnée,
        via l'un de ses rôles.

        Exemple :
            user.has_permission('event.create')
        """
        return self.roles.filter(permissions__codename=codename).exists()

    def get_permissions_codenames(self) -> list[str]:
        """
        Retourne la liste des codes de permissions de l'utilisateur.
        Utile pour le frontend (affichage conditionnel de menus).
        """
        return list(
            self.roles.values_list("permissions__codename", flat=True)
            .exclude(permissions__codename__isnull=True)
            .distinct()
        )
