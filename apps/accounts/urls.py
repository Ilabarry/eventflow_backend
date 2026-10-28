"""
Routes URL de l'application 'accounts'.

Regroupe tous les endpoints d'authentification et de gestion
du compte utilisateur.
"""

from django.urls import path

from apps.accounts.views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshTokenView,
    RegisterView,
    VerifyEmailView,           
    ResendVerificationEmailView,
)

app_name = "accounts"

urlpatterns = [
    # Authentification
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),path("auth/verify-email/", VerifyEmailView.as_view()),
    path("auth/resend-verification/", ResendVerificationEmailView.as_view()),


    # Profil
    path("users/me/", MeView.as_view(), name="me"),
]