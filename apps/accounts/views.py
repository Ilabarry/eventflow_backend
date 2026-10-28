from django.shortcuts import render

"""
Vues API de l'application 'accounts'.

Chaque vue est responsable d'UN endpoint. Elle :
    1. Reçoit la requête HTTP
    2. Valide via un serializer
    3. Appelle un service si logique métier
    4. Retourne une réponse standardisée

Toutes les réponses utilisent l'enveloppe APIResponse.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from apps.accounts.services import AuthService
from common.responses.standard import APIResponse

import logging

logger = logging.getLogger(__name__)


# ==================================================================
# INSCRIPTION
# ==================================================================
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données d'inscription invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        # ✅ NOUVEAU : envoyer l'email de vérification
        try:
            AuthService.send_verification_email(user)
        except Exception:
            logger.exception("Failed to send verification email | user=%s", user.id)
            # On ne bloque pas l'inscription, l'utilisateur pourra demander un renvoi

        return APIResponse.created(
            data=UserSerializer(user).data,
            message="Inscription réussie. Vérifiez votre email pour activer votre compte.",
        )


# ==================================================================
# verification du mail
# ==================================================================
class VerifyEmailView(APIView):
    """
    POST /api/auth/verify-email/
    Body : { "token": "..." }
    Vérifie le token et active le compte.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token", "").strip()
        if not token:
            return APIResponse.error(
                message="Token manquant.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = AuthService.confirm_email_verification(token)
        except ValueError as e:
            return APIResponse.error(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return APIResponse.success(
            data=UserSerializer(user).data,
            message="Email vérifié avec succès. Vous pouvez maintenant vous connecter.",
        )


class ResendVerificationEmailView(APIView):
    """
    POST /api/auth/resend-verification/
    Body : { "email": "..." }
    Renvoie l'email de vérification si le compte existe et n'est pas vérifié.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").lower().strip()
        if not email:
            return APIResponse.error(
                message="Email manquant.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email, is_email_verified=False)
        except User.DoesNotExist:
            # Message générique pour ne pas révéler l'existence du compte
            return APIResponse.success(
                message="Si un compte non vérifié existe avec cet email, un nouveau lien a été envoyé.",
            )

        try:
            AuthService.send_verification_email(user)
        except Exception:
            logger.exception("Failed to resend verification email | user=%s", user.id)
            return APIResponse.error(
                message="Impossible d'envoyer l'email. Réessayez plus tard.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return APIResponse.success(
            message="Un nouveau lien de vérification a été envoyé.",
        )


# ==================================================================
# CONNEXION
# ==================================================================
class LoginView(APIView):
    """
    POST /api/auth/login/

    Authentifie l'utilisateur et retourne une paire access + refresh.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Identifiants invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data["user"]
        tokens = AuthService.generate_tokens_for_user(user)

        return APIResponse.success(
            data={
                "user": UserSerializer(user).data,
                "tokens": tokens,
            },
            message="Connexion réussie.",
        )


# ==================================================================
# REFRESH
# ==================================================================
class RefreshTokenView(APIView):
    """
    POST /api/auth/refresh/

    Rafraîchit l'access token à partir d'un refresh token valide.
    La rotation est activée : un nouveau refresh token est retourné.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return APIResponse.error(
                message="Refresh token manquant.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tokens = AuthService.refresh_access_token(refresh_token)
        except TokenError:
            return APIResponse.error(
                message="Refresh token invalide ou expiré.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        return APIResponse.success(
            data={"tokens": tokens},
            message="Token rafraîchi.",
        )


# ==================================================================
# DÉCONNEXION
# ==================================================================
class LogoutView(APIView):
    """
    POST /api/auth/logout/

    Blackliste le refresh token fourni.
    Idempotent : répond 200 même si le token est absent, expiré ou déjà blacklisté.
    """

    # ✅ Pas d'authentification obligatoire : le logout est best-effort
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        # Pas de token → rien à faire, mais pas d'erreur
        if not refresh_token:
            return APIResponse.success(
                data=None,
                message="Déconnexion effectuée.",
            )

        try:
            AuthService.blacklist_refresh_token(refresh_token)
        except TokenError:
            # Token expiré ou déjà blacklisté : ce n'est pas une erreur
            logger.info("Logout with invalid/expired refresh token")

        return APIResponse.success(
            data=None,
            message="Déconnexion réussie.",
        )


# ==================================================================
# PROFIL UTILISATEUR CONNECTÉ
# ==================================================================
class MeView(APIView):
    """
    GET    /api/users/me/    → Consulter son profil
    PUT    /api/users/me/    → Mettre à jour son profil
    PATCH  /api/users/me/    → Mise à jour partielle
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retourne le profil de l'utilisateur connecté."""
        return APIResponse.success(
            data=UserSerializer(request.user).data,
            message="Profil récupéré.",
        )

    def put(self, request):
        """Met à jour le profil (tous les champs)."""
        return self._update(request, partial=False)

    def patch(self, request):
        """Met à jour partiellement le profil."""
        return self._update(request, partial=True)

    def _update(self, request, partial: bool):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return APIResponse.success(
            data=UserSerializer(request.user).data,
            message="Profil mis à jour.",
        )


# ==================================================================
# CHANGEMENT DE MOT DE PASSE
# ==================================================================
class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/

    Permet à l'utilisateur connecté de changer son mot de passe.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return APIResponse.success(
            data=None,
            message="Mot de passe modifié. Reconnectez-vous.",
        )
