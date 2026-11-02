"""
Serializers de l'application 'accounts'.

Un serializer DRF a deux responsabilités :
    1. Valider les données entrantes (JSON → objet Python)
    2. Transformer les objets Python en JSON (pour la réponse)

On sépare les serializers selon leur usage :
    - RegisterSerializer : inscription
    - UserSerializer : lecture (GET)
    - UserProfileSerializer : mise à jour du profil
    - ChangePasswordSerializer : changement de mot de passe
    - LoginSerializer : connexion
    - LogoutSerializer / RefreshRequestSerializer : tokens
    - VerifyEmailSerializer / ResendVerificationSerializer : vérification d'email

Tous les corps de requête passent par un serializer : un JSON inattendu
(nombre, tableau, objet à la place d'une chaîne) renvoie un 400 propre
au lieu d'une erreur 500.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.constants import SIGNUP_ALLOWED_ROLES
from apps.accounts.models import User
from apps.accounts.services import AuthService
from apps.accounts.validators import (
    validate_password_strength,
    validate_phone_number,
    validate_signup_role,
)

# Taille maximale d'une photo de profil et formats acceptés
PROFILE_PICTURE_MAX_BYTES = 2 * 1024 * 1024  # 2 Mo
PROFILE_PICTURE_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


# ==================================================================
# SERIALIZER : Inscription
# ==================================================================
class RegisterSerializer(serializers.Serializer):
    """
    Serializer pour l'inscription d'un nouvel utilisateur.

    Le mot de passe n'est JAMAIS retourné dans la réponse.
    Seuls les rôles de SIGNUP_ALLOWED_ROLES sont acceptés (jamais 'administrateur').
    """

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=20,
        validators=[validate_phone_number],
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password_strength],
    )
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=SIGNUP_ALLOWED_ROLES,
        default=SIGNUP_ALLOWED_ROLES[0],  # participant par défaut
        validators=[validate_signup_role],
    )

    def validate_email(self, value: str) -> str:
        """Vérifie que l'email n'est pas déjà utilisé."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Un compte avec cet email existe déjà."
            )
        return value.lower()

    def validate_phone(self, value: str) -> str:
        """Vérifie que le téléphone n'est pas déjà utilisé."""
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Un compte avec ce numéro de téléphone existe déjà."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """Mots de passe identiques + validateurs Django (mots de passe courants, etc.)."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Les deux mots de passe ne correspondent pas."}
            )

        validate_password(
            attrs["password"],
            user=User(
                email=attrs["email"],
                first_name=attrs["first_name"],
                last_name=attrs["last_name"],
            ),
        )
        return attrs

    def create(self, validated_data: dict) -> User:
        """Crée l'utilisateur via le service AuthService."""
        validated_data.pop("password_confirm")

        return AuthService.register_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone=validated_data["phone"],
            role_name=validated_data["role"],
        )


# ==================================================================
# SERIALIZER : Lecture utilisateur
# ==================================================================
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer pour lire les informations d'un utilisateur.

    Exclut le mot de passe et autres champs sensibles.
    """

    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "profile_picture",
            "roles",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        """Retourne la liste des noms de rôles de l'utilisateur."""
        return list(obj.roles.values_list("name", flat=True))


# ==================================================================
# SERIALIZER : Mise à jour du profil
# ==================================================================
class UserProfileSerializer(serializers.ModelSerializer):
    """
    Mise à jour du profil de l'utilisateur connecté.

    Champs modifiables : first_name, last_name, phone, profile_picture.
    L'email, les rôles et les drapeaux is_staff / is_superuser ne sont PAS modifiables ici.
    """

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone",
            "profile_picture",
        )
        # Même format de téléphone qu'à l'inscription
        # (l'unicité est vérifiée dans validate_phone ci-dessous).
        extra_kwargs = {
            "phone": {"validators": [validate_phone_number]},
        }

    def validate_phone(self, value: str) -> str:
        """Vérifie que le téléphone n'est pas déjà utilisé par un autre."""
        user = self.context["request"].user
        if User.objects.filter(phone=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )
        return value

    def validate_profile_picture(self, value):
        """Taille et format de la photo (le champ DRF a déjà vérifié que c'est une image)."""
        if value is None:
            return value

        if value.size > PROFILE_PICTURE_MAX_BYTES:
            raise serializers.ValidationError("Image trop lourde (2 Mo maximum).")

        image = getattr(value, "image", None)
        image_format = getattr(image, "format", None)
        if image_format not in PROFILE_PICTURE_ALLOWED_FORMATS:
            raise serializers.ValidationError(
                "Format d'image non autorisé (JPEG, PNG ou WEBP)."
            )
        return value


# ==================================================================
# SERIALIZER : Changement de mot de passe
# ==================================================================
class ChangePasswordSerializer(serializers.Serializer):
    """
    Changement du mot de passe de l'utilisateur connecté.

    Après changement, tous ses refresh tokens sont révoqués (blacklist).
    """

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password_strength],
    )
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value: str) -> str:
        """Vérifie que l'ancien mot de passe est correct."""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "Le mot de passe actuel est incorrect."
            )
        return value

    def validate_new_password(self, value: str) -> str:
        """Validateurs Django (mots de passe courants, similarité avec l'email...)."""
        validate_password(value, self.context["request"].user)
        return value

    def validate(self, attrs: dict) -> dict:
        """Confirmation identique + nouveau mot de passe différent de l'ancien."""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Les deux mots de passe ne correspondent pas."}
            )
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError(
                {"new_password": "Le nouveau mot de passe doit être différent de l'ancien."}
            )
        return attrs

    def save(self, **kwargs) -> User:
        """Applique le changement et révoque toutes les sessions (refresh tokens)."""
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()

        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

        return user


# ==================================================================
# SERIALIZER : Connexion
# ==================================================================
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        email = attrs.get("email", "").lower()
        password = attrs.get("password", "")

        user = AuthService.authenticate_user(email=email, password=password)

        if user is None:
            raise serializers.ValidationError(
                {"non_field_errors": ["Email ou mot de passe incorrect."]}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": ["Ce compte est désactivé."]}
            )

        if not user.is_email_verified:
            raise serializers.ValidationError(
                {"non_field_errors": [
                    "Votre adresse email n'est pas encore vérifiée. "
                    "Consultez votre boîte de réception et cliquez sur le lien d'activation."
                ]}
            )

        attrs["user"] = user
        return attrs


# ==================================================================
# SERIALIZER : Déconnexion (indulgent : "best effort")
# ==================================================================
class LogoutSerializer(serializers.Serializer):
    """
    Corps de la requête de déconnexion.

    Le refresh token est optionnel : la déconnexion reste idempotente
    (un token absent, expiré ou déjà révoqué n'est pas une erreur).
    Seul un type incorrect (nombre, tableau...) renvoie 400.
    """

    refresh = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2048,
    )


# ==================================================================
# SERIALIZER : Refresh
# ==================================================================
class RefreshRequestSerializer(serializers.Serializer):
    """Corps de la requête de rafraîchissement."""

    refresh = serializers.CharField(max_length=2048)


# ==================================================================
# SERIALIZERS : Vérification d'email
# ==================================================================
class VerifyEmailSerializer(serializers.Serializer):
    """Corps de la requête de vérification d'email."""

    token = serializers.CharField(max_length=512)


class ResendVerificationSerializer(serializers.Serializer):
    """Corps de la requête de renvoi de l'email de vérification."""

    email = serializers.EmailField()