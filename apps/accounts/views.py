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


# ==================================================================
# INSCRIPTION
# ==================================================================
class RegisterView(APIView):
    """
    POST /api/auth/register/

    Crée un nouvel utilisateur. Le rôle est choisi par l'utilisateur
    ('participant' ou 'organisateur').
    """

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
        return APIResponse.created(
            data=UserSerializer(user).data,
            message="Inscription réussie. Vous pouvez maintenant vous connecter.",
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

    Blackliste le refresh token. L'access token expirera naturellement
    (courte durée).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            AuthService.blacklist_refresh_token(serializer.validated_data["refresh"])
        except TokenError:
            return APIResponse.error(
                message="Refresh token invalide ou expiré.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

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
