"""
Commande de management : create_admin

Crée le superutilisateur admin d'EVENTFLOW.

Utilisée automatiquement lors du déploiement Render (buildCommand),
car le plan gratuit ne donne pas toujours accès au Shell.

Variables d'environnement :
    ADMIN_EMAIL      : email du compte admin (obligatoire).
    ADMIN_PASSWORD   : mot de passe initial (obligatoire à la création).
    ADMIN_RESET_PASSWORD : "true" pour réinitialiser le mot de passe d'un
                       compte existant (jamais fait implicitement).
    ADMIN_FIRST_NAME / ADMIN_LAST_NAME / ADMIN_PHONE : champs de profil.
    ADMIN_ROLE       : nom du rôle (défaut : "administrateur").

⚠️ Aucun mot de passe par défaut n'est fourni. La commande échoue
explicitement si ADMIN_EMAIL ou ADMIN_PASSWORD manquent, plutôt que de
créer un compte avec des identifiants connus de tous.

Usage :
    python manage.py create_admin
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role

User = get_user_model()


class Command(BaseCommand):
    help = "Crée le superutilisateur admin EVENTFLOW (email vérifié forcé à True)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-configured",
            action="store_true",
            help=(
                "En mode déploiement : si ADMIN_EMAIL, ADMIN_PASSWORD ou "
                "ADMIN_PHONE manquent, affiche un avertissement et ignore la "
                "commande au lieu de faire échouer le build."
            ),
        )

    def _abort_or_skip(self, message: str, if_configured: bool) -> bool:
        """Renvoie True si la commande doit s'arrêter sans erreur."""
        if if_configured:
            self.stdout.write(
                self.style.WARNING(
                    f"ATTENTION : {message} Commande create_admin ignorée "
                    "(option --if-configured)."
                )
            )
            return True
        raise CommandError(message)

    def handle(self, *args, **options):
        if_configured = options.get("if_configured", False)
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        reset_password = os.environ.get("ADMIN_RESET_PASSWORD", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        first_name = os.environ.get("ADMIN_FIRST_NAME", "Admin")
        last_name = os.environ.get("ADMIN_LAST_NAME", "Eventflow")
        phone = os.environ.get("ADMIN_PHONE", "").strip()
        role_name = os.environ.get("ADMIN_ROLE", "administrateur")

        if not email:
            if self._abort_or_skip(
                "ADMIN_EMAIL est obligatoire. Définissez-le dans l'environnement "
                "avant de lancer create_admin.",
                if_configured,
            ):
                return

        user = User.objects.filter(email=email).first()
        created = user is None

        if created and not password:
            if self._abort_or_skip(
                "ADMIN_PASSWORD est obligatoire pour créer le compte admin. "
                "Aucun mot de passe par défaut n'est utilisé.",
                if_configured,
            ):
                return

        if created and not phone:
            if self._abort_or_skip(
                "ADMIN_PHONE est obligatoire pour créer le compte admin "
                "(le champ téléphone est unique et non nul).",
                if_configured,
            ):
                return

        if created:
            user = User.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                is_staff=True,
                is_superuser=True,
                is_active=True,
                is_email_verified=True,
            )
            user.set_password(password)
            user.save()
        else:
            # Ne jamais réactiver ni réinitialiser un compte existant sans
            # demande explicite : le build Render s'exécute à chaque déploiement.
            user.first_name = first_name
            user.last_name = last_name
            if phone:
                # Ne jamais écraser un téléphone existant par une valeur vide.
                user.phone = phone
            user.is_staff = True
            user.is_superuser = True
            user.is_email_verified = True

            if reset_password:
                if not password:
                    raise CommandError(
                        "ADMIN_RESET_PASSWORD=true exige ADMIN_PASSWORD."
                    )
                user.set_password(password)
                user.is_active = True

            user.save()

            if not reset_password:
                self.stdout.write(
                    self.style.WARNING(
                        "Mot de passe du compte existant conservé "
                        "(ADMIN_RESET_PASSWORD non activé)."
                    )
                )

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
