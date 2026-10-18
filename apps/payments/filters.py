"""
Filtres django-filter pour les paiements.
"""

import django_filters

from apps.payments.constants import PaymentMethod, PaymentProvider, PaymentStatus
from apps.payments.models import Payment


class PaymentFilter(django_filters.FilterSet):
    """Filtre pour la liste des paiements."""

    status = django_filters.ChoiceFilter(choices=PaymentStatus.choices)
    payment_method = django_filters.ChoiceFilter(choices=PaymentMethod.choices)
    provider = django_filters.ChoiceFilter(choices=PaymentProvider.choices)
    registration = django_filters.UUIDFilter(field_name="registration__id")
    event = django_filters.UUIDFilter(field_name="registration__event__id")
    participant = django_filters.UUIDFilter(field_name="registration__participant__id")
    transaction_reference = django_filters.CharFilter(lookup_expr="iexact")
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Recherche par référence, email du participant ou référence provider.",
    )

    class Meta:
        model = Payment
        fields = ["status", "payment_method", "provider"]

    def filter_search(self, queryset, name, value):
        if value:
            from django.db.models import Q

            return queryset.filter(
                Q(transaction_reference__icontains=value)
                | Q(provider_reference__icontains=value)
                | Q(registration__participant__email__icontains=value)
                | Q(registration__reference__icontains=value)
            )
        return queryset