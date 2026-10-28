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
    - LoginSerializer : connexion (Phase 3)
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.constants import SIGNUP_ALLOWED_ROLES
from apps.accounts.services import AuthService
from apps.accounts.validators import (
    validate_password_strength,
    validate_phone_number,
    validate_signup_role,
)

User = get_user_model()


# ==================================================================
# SERIALIZER : Inscription
# ==================================================================
class RegisterSerializer(serializers.Serializer):
    """
    Serializer pour l'inscription d'un nouvel utilisateur.

    Champs :
        - first_name : prénom (obligatoire)
        - last_name : nom (obligatoire)
        - email : email unique (obligatoire)
        - phone : téléphone unique (obligatoire)
        - password : mot de passe (obligatoire, write_only)
        - password_confirm : confirmation (obligatoire, write_only)
        - role : rôle choisi parmi SIGNUP_ALLOWED_ROLES

    Le mot de passe n'est JAMAIS retourné dans la réponse.
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

    # ------------------------------------------------------------------
    # Validations globales (au niveau de l'objet, pas du champ)
    # ------------------------------------------------------------------
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
        """Vérifie que les deux mots de passe correspondent."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Les deux mots de passe ne correspondent pas."}
            )
        return attrs

    # ------------------------------------------------------------------
    # Création (appel du service)
    # ------------------------------------------------------------------
    def create(self, validated_data: dict) -> User:
        """Crée l'utilisateur via le service AuthService."""
        # On retire password_confirm, non utilisé pour la création
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

    Utilisé pour GET /api/users/me/ et les réponses d'inscription.

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
        read_only_fields = fields  # Tous les champs sont en lecture seule ici

    def get_roles(self, obj: User) -> list[str]:
        """Retourne la liste des noms de rôles de l'utilisateur."""
        return list(obj.roles.values_list("name", flat=True))


# ==================================================================
# SERIALIZER : Mise à jour du profil
# ==================================================================
class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer pour mettre à jour le profil de l'utilisateur connecté.

    Champs modifiables :
        - first_name
        - last_name
        - phone
        - profile_picture

    L'email n'est PAS modifiable ici (nécessite une procédure spéciale).
    """

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone",
            "profile_picture",
        )

    def validate_phone(self, value: str) -> str:
        """Vérifie que le téléphone n'est pas déjà utilisé par un autre."""
        user = self.context["request"].user
        if User.objects.filter(phone=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )
        return value


# ==================================================================
# SERIALIZER : Changement de mot de passe
# ==================================================================
class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer pour changer le mot de passe de l'utilisateur connecté.

    Champs :
        - old_password : mot de passe actuel
        - new_password : nouveau mot de passe
        - new_password_confirm : confirmation
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

    def validate(self, attrs: dict) -> dict:
        """Vérifie que les nouveaux mots de passe correspondent."""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Les deux mots de passe ne correspondent pas."}
            )
        return attrs

    def save(self, **kwargs) -> User:
        """Applique le changement de mot de passe."""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
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

        from apps.accounts.services import AuthService

        # ✅ Appeler la méthode de AuthService
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
# SERIALIZER : Déconnexion
# ==================================================================
class LogoutSerializer(serializers.Serializer):
    """
    Serializer pour la déconnexion.

    L'utilisateur envoie son refresh token pour le blacklister.
    """

    refresh = serializers.CharField()

    def validate_refresh(self, value: str) -> str:
        """Vérifie que le refresh token est valide."""
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError(
                "Refresh token invalide ou expiré."
            )
        return value