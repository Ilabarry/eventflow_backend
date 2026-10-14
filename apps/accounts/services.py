"""
Services métier de l'application 'accounts'.
"""

from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

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

        Retourne l'utilisateur si les identifiants sont valides et
        que le compte est actif, sinon None.
        """
        # Django utilise USERNAME_FIELD ('email') pour l'authentification
        user = authenticate(request=None, username=email, password=password)
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