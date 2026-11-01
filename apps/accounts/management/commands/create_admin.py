"""
Commande de management : create_admin

Crée (ou met à jour) le superutilisateur admin d'EVENTFLOW.

Utilisée automatiquement lors du déploiement Render (buildCommand),
car le plan gratuit ne donne pas accès au Shell.

Usage :
    python manage.py create_admin
"""
import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.accounts.models import Role

User = get_user_model()


class Command(BaseCommand):
    help = "Crée le superutilisateur admin EVENTFLOW (email vérifié forcé à True)."

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL", "admin@eventflow.com")
        password = os.environ.get("ADMIN_PASSWORD", "Adminevent@adminflow@admin2026")
        first_name = os.environ.get("ADMIN_FIRST_NAME", "Admin")
        last_name = os.environ.get("ADMIN_LAST_NAME", "Eventflow")
        phone = os.environ.get("ADMIN_PHONE", "+221783249424")
        role_name = os.environ.get("ADMIN_ROLE", "administrateur")

        # 1. Créer ou récupérer l'utilisateur (sans le rôle M2M)
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "is_email_verified": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
        else:
            # Mise à jour des champs critiques si le compte existe déjà
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.is_email_verified = True
            user.set_password(password)
            user.save()

        # 2. Attribuer le rôle (relation ManyToMany)
        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": "Administrateur de la plateforme EVENTFLOW"},
        )
        user.roles.add(role)

        action = "créé" if created else "mis à jour"
        self.stdout.write(self.style.SUCCESS(
            f"✓ Superutilisateur {action} : {email} (rôle : {role_name})"
        ))