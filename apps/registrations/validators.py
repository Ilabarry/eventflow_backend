"""
Validateurs du module Registration.

Les validateurs sont des fonctions réutilisables qui lèvent
ValidationError (Django) que DRF convertit automatiquement en 400.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.events.constants import EventStatus, ParticipationType


# ==================================================================
# VALIDATION : Événement prêt à recevoir des inscriptions
# ==================================================================
def validate_event_is_open(event) -> None:
    """
    Vérifie que l'événement accepte des inscriptions.

    Règles :
        - status = PUBLISHED (pas DRAFT, pas CANCELLED, pas COMPLETED)
        - end_at > now() (pas encore terminé)
    """
    if event is None:
        raise ValidationError(_("L'événement est obligatoire."))

    if event.status == EventStatus.DRAFT:
        raise ValidationError(
            _("Cet événement n'est pas encore publié."),
            code="event_not_published",
        )

    if event.status == EventStatus.CANCELLED:
        raise ValidationError(
            _("Cet événement a été annulé."),
            code="event_cancelled",
        )

    if event.status == EventStatus.COMPLETED:
        raise ValidationError(
            _("Cet événement est terminé."),
            code="event_completed",
        )

    if event.end_at and event.end_at < timezone.now():
        raise ValidationError(
            _("Cet événement est déjà terminé."),
            code="event_already_ended",
        )


# ==================================================================
# VALIDATION : Type de participation
# ==================================================================
def validate_participation_type(event, ticket_type=None) -> None:
    """
    Vérifie que le type de participation est cohérent.

    Règles :
        - FREE : pas de ticket_type requis.
        - PAID : ticket_type requis.

    Raises:
        ValidationError: Si le type de participation est incohérent.
    """
    if event is None:
        return

    if event.participation_type == ParticipationType.PAID:
        if ticket_type is None:
            raise ValidationError(
                _(
                    "Cet événement est payant. Vous devez sélectionner "
                    "un type de ticket."
                ),
                code="ticket_type_required",
            )