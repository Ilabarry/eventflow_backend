"""
Validateurs du module Tickets.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.events.constants import ParticipationType
from apps.tickets.models import TicketType


def validate_ticket_type_price(ticket_type: TicketType) -> None:
    """Vérifie que le prix est cohérent avec le type d'événement."""
    if not ticket_type.event:
        raise ValidationError(_("L'événement est obligatoire."))

    # Événement gratuit : prix doit être 0
    if ticket_type.event.participation_type == ParticipationType.FREE:
        if ticket_type.price != 0:
            raise ValidationError(
                _("Un événement gratuit doit avoir un prix de 0."),
                code="free_event_price_must_be_zero",
            )


def validate_sales_window(sales_start_at, sales_end_at) -> None:
    """Vérifie la cohérence de la période de vente."""
    if sales_start_at and sales_end_at and sales_start_at >= sales_end_at:
        raise ValidationError(
            _("La date de début des ventes doit être antérieure à la date de fin."),
            code="invalid_sales_window",
        )


def validate_ticket_type_can_be_modified(ticket_type: TicketType, validated_data: dict) -> None:
    """
    Vérifie qu'un TicketType peut être modifié.

    Règle : si des tickets ont été vendus, on ne peut plus modifier
    le prix (snapshot historique).
    """
    if ticket_type.quantity_sold > 0 and "price" in validated_data:
        new_price = validated_data["price"]
        if new_price != ticket_type.price:
            raise ValidationError(
                _("Le prix ne peut plus être modifié : des tickets ont déjà été vendus."),
                code="price_locked_after_sale",
            )