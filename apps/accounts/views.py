"""
Vues API de l'application 'accounts'.

Chaque vue est responsable d'UN endpoint. Elle :
    1. Reçoit la requête HTTP
    2. Valide via un serializer (JAMAIS request.data.get(...) directement)
    3. Appelle un service si logique métier
    4. Retourne une réponse standardisée

Toutes les réponses utilisent l'enveloppe APIResponse.

Limitation de débit : chaque vue sensible déclare un `throttle_scope`.
Les taux correspondants DOIVENT exister dans
settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], sinon DRF lève
ImproperlyConfigured (erreur 500).
"""

import logging

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.models import User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshRequestSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserProfileSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from apps.accounts.services import AuthService
from common.responses.standard import APIResponse
from common.throttles import EmailScopedThrottle, ResendEmailTargetThrottle

logger = logging.getLogger(__name__)


# ==================================================================
# INSCRIPTION
# ==================================================================
class RegisterView(APIView):
    """POST /api/auth/register/"""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données d'inscription invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = serializer.save()
        except IntegrityError:
            # Course : deux inscriptions simultanées avec le même email/téléphone
            return APIResponse.error(
                message="Un compte avec cet email ou ce numéro de téléphone existe déjà.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Envoyer l'email de vérification (sans bloquer l'inscription en cas d'échec)
        try:
            AuthService.send_verification_email(user)
        except Exception:
            logger.exception("Failed to send verification email | user=%s", user.id)

        return APIResponse.created(
            data=UserSerializer(user).data,
            message="Inscription réussie. Vérifiez votre email pour activer votre compte.",
        )


# ==================================================================
# VÉRIFICATION DE L'EMAIL
# ==================================================================
class VerifyEmailView(APIView):
    """
    POST /api/auth/verify-email/
    Body : { "token": "..." }
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_verify"

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Token manquant ou invalide.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = AuthService.confirm_email_verification(
                serializer.validated_data["token"].strip()
            )
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

    Réponse TOUJOURS identique (compte existant ou non, envoi réussi ou non),
    pour ne pas révéler l'existence d'un compte.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, ResendEmailTargetThrottle]
    throttle_scope = "auth_email"

    GENERIC_MESSAGE = (
        "Si un compte non vérifié existe avec cet email, "
        "un nouveau lien a été envoyé."
    )

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Email manquant ou invalide.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"].lower().strip()
        # Ne jamais renvoyer de lien à un compte désactivé/suspendu.
        user = User.objects.filter(
            email__iexact=email,
            is_email_verified=False,
            is_active=True,
        ).first()

        if user is not None:
            try:
                AuthService.send_verification_email(user)
            except Exception:
                # On logue côté serveur, mais la réponse reste identique
                logger.exception(
                    "Failed to resend verification email | user=%s", user.id
                )

        return APIResponse.success(message=self.GENERIC_MESSAGE)


# ==================================================================
# CONNEXION
# ==================================================================
class LoginView(APIView):
    """
    POST /api/auth/login/

    Authentifie l'utilisateur et retourne une paire access + refresh.
    Limites : par IP (auth_login) ET par email ciblé (auth_login_email).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, EmailScopedThrottle]
    throttle_scope = "auth_login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: None},
    )
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

    Échange un refresh token contre une nouvelle paire (rotation réelle) :
    l'ancien refresh token est révoqué et ne peut plus être réutilisé.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"

    def post(self, request):
        serializer = RefreshRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Refresh token manquant ou invalide.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tokens = AuthService.refresh_access_token(
                serializer.validated_data["refresh"]
            )
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

    # Pas d'authentification obligatoire : le logout est "best effort"
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_logout"

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        refresh_token = serializer.validated_data.get("refresh", "")

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

    Change le mot de passe et révoque toutes les sessions (refresh tokens).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password"

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