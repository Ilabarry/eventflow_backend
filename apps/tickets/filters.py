"""
Filtres django-filter pour les tickets et types de tickets.
"""

import django_filters

from apps.tickets.constants import TicketStatus
from apps.tickets.models import Ticket, TicketType


class TicketFilter(django_filters.FilterSet):
    """Filtre pour la liste des tickets."""

    status = django_filters.ChoiceFilter(choices=TicketStatus.choices)
    event = django_filters.UUIDFilter(field_name="registration__event__id")
    participant = django_filters.UUIDFilter(field_name="registration__participant__id")
    ticket_type = django_filters.UUIDFilter(field_name="ticket_type__id")
    reference = django_filters.CharFilter(lookup_expr="iexact")
    issued_after = django_filters.DateFilter(field_name="issued_at", lookup_expr="date__gte")
    issued_before = django_filters.DateFilter(field_name="issued_at", lookup_expr="date__lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Ticket
        fields = ["status", "ticket_type"]

    def filter_search(self, queryset, name, value):
        if value:
            from django.db.models import Q
            return queryset.filter(
                Q(reference__icontains=value)
                | Q(registration__reference__icontains=value)
                | Q(registration__participant__email__icontains=value)
            )
        return queryset


class TicketTypeFilter(django_filters.FilterSet):
    """Filtre pour la liste des types de tickets."""

    event = django_filters.UUIDFilter(field_name="event__id")
    is_active = django_filters.BooleanFilter()
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    available = django_filters.BooleanFilter(method="filter_available")

    class Meta:
        model = TicketType
        fields = ["event", "is_active"]

    def filter_available(self, queryset, name, value):
        """Filtre les TicketTypes avec quantité disponible."""
        if value:
            from django.db import models
            return queryset.filter(
                models.Q(quantity_total__isnull=True)
                | models.Q(quantity_sold__lt=models.F("quantity_total"))
            )
        return queryset