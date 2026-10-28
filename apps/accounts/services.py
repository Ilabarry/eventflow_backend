"""
Services métier de l'application 'accounts'.
"""

from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from django.core import signing
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Durée de validité du lien de vérification: 24h
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24

from apps.accounts.constants import (
    DEFAULT_ROLE_ON_SIGNUP,
    ROLE_DESCRIPTIONS,
)
from apps.accounts.models import Role, User


class AuthService:
    """
    Service d'authentification : inscription, connexion, tokens.
    """

    # ------------------------------------------------------------------
    # Inscription
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def register_user(
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: str,
        role_name: str = DEFAULT_ROLE_ON_SIGNUP,
    ) -> User:
        """Crée un nouvel utilisateur et lui attribue le rôle choisi."""
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )

        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": ROLE_DESCRIPTIONS.get(role_name, "")},
        )
        user.roles.add(role)

        return user

    # ------------------------------------------------------------------
    # Ajout de rôle (cumul)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def add_role_to_user(*, user: User, role_name: str) -> User:
        """Ajoute un rôle à un utilisateur existant (cumul de rôles)."""
        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": ROLE_DESCRIPTIONS.get(role_name, "")},
        )
        user.roles.add(role)
        return user

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------
    @staticmethod
    def authenticate_user(*, email: str, password: str) -> User | None:
        """
        Authentifie un utilisateur par email + mot de passe.

        ⚠️ On n'utilise PAS authenticate() seul car il retourne None
        pour les comptes inactifs, ce qui masque la vraie raison
        de l'échec (mot de passe vs compte désactivé).
        """
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None

        if not user.check_password(password):
            return None

        return user

    @staticmethod
    def generate_tokens_for_user(user: User) -> dict:
        """
        Génère une paire access + refresh token pour un utilisateur.

        Returns:
            {
                "access": "...",
                "refresh": "..."
            }
        """
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }

    # ------------------------------------------------------------------
    # VÉRIFICATION EMAIL
    # ------------------------------------------------------------------
    @staticmethod
    def generate_email_verification_token(user) -> str:
        """
        Génère un token signé pour la vérification d'email.
        Le token contient l'ID de l'utilisateur et expire après 24h.
        Aucun stockage en base n'est nécessaire.
        """
        return signing.dumps(
            {"user_id": str(user.id)},
            salt="email-verification",
        )

    @staticmethod
    def verify_email_token(token: str) -> User:
        """
        Vérifie un token et retourne l'utilisateur correspondant.
        Lève une exception si le token est invalide ou expiré.
        """
        try:
            data = signing.loads(
                token,
                salt="email-verification",
                max_age=EMAIL_VERIFICATION_MAX_AGE,
            )
        except signing.SignatureExpired:
            raise ValueError("Le lien de vérification a expiré. Demandez-en un nouveau.")
        except signing.BadSignature:
            raise ValueError("Le lien de vérification est invalide.")

        try:
            user = User.objects.get(pk=data["user_id"])
        except User.DoesNotExist:
            raise ValueError("Utilisateur introuvable.")

        return user

    @staticmethod
    def send_verification_email(user) -> None:
        """
        Envoie l'email de vérification à l'utilisateur.
        Utilise un template HTML professionnel avec fallback texte.
        """
        token = AuthService.generate_email_verification_token(user)
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:4200")
        verification_url = f"{frontend_url}/verify-email?token={token}"

        context = {
            "first_name": user.first_name,
            "verification_url": verification_url,
            "current_year": timezone.now().year,
        }

        subject = "Vérifiez votre adresse email — EVENTFLOW"

        # Version texte (fallback)
        text_body = render_to_string("emails/verify_email.txt", context)

        # Version HTML (design)
        html_body = render_to_string("emails/verify_email.html", context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()

        logger.info(
            "Verification email sent | user=%s | email=%s",
            user.id, user.email,
        )

    @staticmethod
    def confirm_email_verification(token: str) -> User:
        """
        Vérifie le token et active le compte.
        Idempotent : si déjà vérifié, retourne l'utilisateur sans erreur.
        """
        user = AuthService.verify_email_token(token)

        if user.is_email_verified:
            return user  # Déjà vérifié, on ne fait rien

        user.is_email_verified = True
        user.is_active = True   # Activer le compte
        user.save(update_fields=["is_email_verified", "is_active"])
        logger.info("Email verified | user=%s", user.id)
        return user

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    @staticmethod
    def refresh_access_token(refresh_token_str: str) -> dict:
        """
        Rafraîchit un access token à partir d'un refresh token.

        Args:
            refresh_token_str: Le refresh token envoyé par le client.

        Returns:
            {"access": "...", "refresh": "..."}

        Raises:
            TokenError: Si le refresh token est invalide, expiré ou blacklisté.
        """
        try:
            refresh = RefreshToken(refresh_token_str)
            return {
                "access": str(refresh.access_token),
                "refresh": str(refresh),  # Rotation activée dans settings
            }
        except TokenError:
            raise

    # ------------------------------------------------------------------
    # Déconnexion
    # ------------------------------------------------------------------
    @staticmethod
    def blacklist_refresh_token(refresh_token_str: str) -> None:
        """
        Blackliste un refresh token (déconnexion).

        Args:
            refresh_token_str: Le refresh token à révoquer.

        Raises:
            TokenError: Si le token est invalide.
        """
        try:
            token = RefreshToken(refresh_token_str)
            token.blacklist()
        except TokenError:
            raise


