"""
Filtres django-filter pour les certificats.
"""

import django_filters

from apps.certificates.constants import CertificateStatus
from apps.certificates.models import Certificate


class CertificateFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=CertificateStatus.choices)
    event = django_filters.UUIDFilter(field_name="registration__event__id")
    issued_after = django_filters.IsoDateTimeFilter(
        field_name="issued_at", lookup_expr="gte"
    )
    issued_before = django_filters.IsoDateTimeFilter(
        field_name="issued_at", lookup_expr="lte"
    )
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Certificate
        fields = ["status"]

    def filter_search(self, queryset, name, value):
        if value:
            from django.db.models import Q
            return queryset.filter(
                Q(reference__icontains=value)
                | Q(registration__participant__email__icontains=value)
                | Q(registration__participant__first_name__icontains=value)
                | Q(registration__participant__last_name__icontains=value)
            )
        return queryset