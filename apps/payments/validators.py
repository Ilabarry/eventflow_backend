"""
Validateurs du module Payment.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.events.constants import ParticipationType
from apps.payments.constants import PaymentMethod, PaymentProvider
from apps.registrations.constants import RegistrationStatus


def validate_registration_payable(registration) -> None:
    """Vérifie qu'une inscription peut faire l'objet d'un paiement."""
    if registration is None:
        raise ValidationError(_("L'inscription est obligatoire."))

    if registration.status != RegistrationStatus.PENDING:
        raise ValidationError(
            _("Seule une inscription PENDING peut être payée."),
            code="registration_not_pending",
        )

    if registration.event.participation_type == ParticipationType.FREE:
        raise ValidationError(
            _("Cet événement est gratuit, aucun paiement n'est requis."),
            code="event_is_free",
        )


def validate_payment_method(value: str) -> None:
    """Vérifie que la méthode de paiement est autorisée."""
    if value not in PaymentMethod.values:
        raise ValidationError(
            _("Méthode de paiement invalide."),
            code="invalid_payment_method",
        )


def validate_provider(value: str) -> None:
    """Vérifie que le provider est autorisé."""
    if value not in PaymentProvider.values:
        raise ValidationError(
            _("Provider de paiement invalide."),
            code="invalid_provider",
        )