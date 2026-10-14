"""
Validateurs personnalisés pour l'application 'accounts'.

Ces validateurs sont utilisés par les serializers pour vérifier
que les données respectent les règles métier.

Un validateur est une fonction qui prend une valeur en entrée et
lève une ValidationError si la valeur est invalide. DRF l'attrape
automatiquement et renvoie une réponse 400 avec le message.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.accounts.constants import PHONE_MAX_LENGTH, SIGNUP_ALLOWED_ROLES


# ------------------------------------------------------------------
# Validation du rôle à l'inscription
# ------------------------------------------------------------------
def validate_signup_role(value: str) -> None:
    """
    Vérifie que le rôle fourni à l'inscription est autorisé.

    Autorisés : 'participant', 'organisateur'
    Interdit : 'administrateur' (seul un admin peut l'attribuer)

    Args:
        value: Le nom du rôle choisi par l'utilisateur.

    Raises:
        ValidationError: Si le rôle n'est pas autorisé.
    """
    if value not in SIGNUP_ALLOWED_ROLES:
        raise ValidationError(
            _(
                "Le rôle '%(value)s' n'est pas autorisé à l'inscription. "
                "Choisissez parmi : %(allowed)s."
            ),
            params={
                "value": value,
                "allowed": ", ".join(SIGNUP_ALLOWED_ROLES),
            },
            code="invalid_signup_role",
        )


# ------------------------------------------------------------------
# Validation du numéro de téléphone (format international)
# ------------------------------------------------------------------
# Format accepté : +221771234567, +33612345678, 00221771234567
PHONE_REGEX = re.compile(r"^\+?[0-9]{8,15}$")


def validate_phone_number(value: str) -> None:
    """
    Vérifie que le numéro de téléphone a un format valide.

    Format accepté :
        - Commence par '+' (optionnel)
        - Contient entre 8 et 15 chiffres
        - Pas d'espaces, pas de tirets, pas de parenthèses

    Exemples valides :
        +221771234567
        00221771234567
        771234567

    Exemples invalides :
        77 123 45 67     (espaces)
        +221-77-123-4567 (tirets)
        abc123           (lettres)

    Args:
        value: Le numéro de téléphone.

    Raises:
        ValidationError: Si le format est invalide.
    """
    if not value:
        raise ValidationError(_("Le numéro de téléphone est obligatoire."))

    if len(value) > PHONE_MAX_LENGTH:
        raise ValidationError(
            _("Le numéro de téléphone ne peut pas dépasser %(max)d caractères."),
            params={"max": PHONE_MAX_LENGTH},
        )

    if not PHONE_REGEX.match(value):
        raise ValidationError(
            _(
                "Le numéro de téléphone doit contenir entre 8 et 15 chiffres, "
                "avec un '+' optionnel au début (ex: +221771234567)."
            ),
            code="invalid_phone_format",
        )


# ------------------------------------------------------------------
# Validation du mot de passe (force minimale)
# ------------------------------------------------------------------
def validate_password_strength(value: str) -> None:
    """
    Vérifie que le mot de passe respecte une politique minimale de sécurité.

    Règles :
        - Au moins 8 caractères
        - Au moins une lettre minuscule
        - Au moins une lettre majuscule
        - Au moins un chiffre

    Note : Django applique déjà ses propres validateurs
    (AUTH_PASSWORD_VALIDATORS dans settings.py). Cette fonction
    ajoute une couche supplémentaire côté métier.
    """
    if len(value) < 8:
        raise ValidationError(
            _("Le mot de passe doit contenir au moins 8 caractères."),
            code="password_too_short",
        )

    if not re.search(r"[a-z]", value):
        raise ValidationError(
            _("Le mot de passe doit contenir au moins une lettre minuscule."),
            code="password_no_lowercase",
        )

    if not re.search(r"[A-Z]", value):
        raise ValidationError(
            _("Le mot de passe doit contenir au moins une lettre majuscule."),
            code="password_no_uppercase",
        )

    if not re.search(r"\d", value):
        raise ValidationError(
            _("Le mot de passe doit contenir au moins un chiffre."),
            code="password_no_digit",
        )