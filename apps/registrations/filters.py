"""
Filtres django-filter pour les inscriptions.
"""

import django_filters

from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration


class RegistrationFilter(django_filters.FilterSet):
    """Filtre pour la liste des inscriptions."""

    status = django_filters.ChoiceFilter(choices=RegistrationStatus.choices)
    event = django_filters.UUIDFilter(field_name="event__id")
    participant = django_filters.UUIDFilter(field_name="participant__id")
    reference = django_filters.CharFilter(lookup_expr="iexact")
    registered_after = django_filters.DateFilter(
        field_name="registered_at", lookup_expr="date__gte",
    )
    registered_before = django_filters.DateFilter(
        field_name="registered_at", lookup_expr="date__lte",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Recherche par référence, email ou nom du participant.",
    )

    class Meta:
        model = Registration
        fields = ["status", "event", "participant", "reference"]

    def filter_search(self, queryset, name, value):
        """Recherche par référence, email ou nom du participant."""
        if value:
            from django.db.models import Q

            return queryset.filter(
                Q(reference__icontains=value)
                | Q(participant__email__icontains=value)
                | Q(participant__first_name__icontains=value)
                | Q(participant__last_name__icontains=value)
            )
        return queryset