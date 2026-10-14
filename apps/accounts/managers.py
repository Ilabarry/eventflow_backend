"""
Gestionnaire personnalisé pour le modèle User.

Django fournit un UserManager par défaut (django.contrib.auth.models.UserManager)
mais celui-ci est basé sur 'username'. Comme notre modèle User utilise 'email'
comme identifiant (USERNAME_FIELD = 'email'), nous devons fournir notre propre
manager.

Deux méthodes sont OBLIGATOIRES pour que Django fonctionne :
    - create_user(email, password, **extra_fields)
    - create_superuser(email, password, **extra_fields)
"""

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Manager pour le modèle User basé sur l'email.

    Hérite de BaseUserManager pour bénéficier des utilitaires Django
    (normalisation d'email, hash de mot de passe, etc.).
    """

    use_in_migrations = True  # Permet d'utiliser ce manager dans les migrations

    # ------------------------------------------------------------------
    # Méthodes internes (privées)
    # ------------------------------------------------------------------
    def _create_user(self, email, password, **extra_fields):
        """
        Logique commune à create_user et create_superuser.

        Étapes :
            1. Vérifier que l'email est fourni
            2. Normaliser l'email (minuscules, domaine en minuscules)
            3. Créer l'instance (sans mot de passe en clair)
            4. Hasher le mot de passe
            5. Sauvegarder en base
        """
        if not email:
            raise ValueError(_("L'adresse email est obligatoire."))

        # Normalisation : "ILA@Example.COM" -> "ila@example.com"
        email = self.normalize_email(email)

        # Création de l'instance User
        user = self.model(email=email, **extra_fields)

        # Hash sécurisé du mot de passe (jamais de mot de passe en clair !)
        user.set_password(password)

        # Sauvegarde en base de données
        user.save(using=self._db)
        return user

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def create_user(self, email, password=None, **extra_fields):
        """
        Crée un utilisateur standard (non-staff, non-superuser).

        Utilisé par :
            - Le RegisterSerializer (inscription publique)
            - Les fixtures de test
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Crée un superutilisateur (accès admin Django complet).

        Utilisé par :
            - La commande 'python manage.py createsuperuser'
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        # Sécurité : on s'assure que les flags sont bien à True
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Un superuser doit avoir is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Un superuser doit avoir is_superuser=True."))

        return self._create_user(email, password, **extra_fields)