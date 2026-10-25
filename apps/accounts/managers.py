from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_("L'adresse email est obligatoire."))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Un superuser doit avoir is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Un superuser doit avoir is_superuser=True."))

        # ✅ Créer l'utilisateur d'abord
        user = self._create_user(email, password, **extra_fields)

        # ✅ Puis lui attribuer le rôle administrateur
        # Import local pour éviter les imports circulaires
        from apps.accounts.constants import ROLE_ADMIN, ROLE_DESCRIPTIONS
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(
            name=ROLE_ADMIN,
            defaults={"description": ROLE_DESCRIPTIONS.get(ROLE_ADMIN, "")},
        )
        user.roles.add(role)

        return user