"""
Filtres des listes de supervision.

Phase S1 : journal d'audit.
    ?action=USER_SUSPENDED   ?entity_type=USER   ?entity_id=<uuid>
    ?actor=<uuid>            ?result=DENIED
    ?date_from=2026-10-01    ?date_to=2026-10-31   (dates incluses)
    ?search=awa              (e-mail de l'acteur, description, raison)
    ?ordering=-created_at    (liste blanche : created_at, action)
"""

import django_filters
from django.db.models import Q

from apps.supervision.constants import AuditAction, AuditEntity, AuditResult
from apps.supervision.models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    action = django_filters.ChoiceFilter(choices=AuditAction.choices)
    entity_type = django_filters.ChoiceFilter(choices=AuditEntity.choices)
    entity_id = django_filters.CharFilter()
    actor = django_filters.UUIDFilter(field_name="actor_id")
    result = django_filters.ChoiceFilter(choices=AuditResult.choices)
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    search = django_filters.CharFilter(method="filter_search")
    ordering = django_filters.OrderingFilter(
        fields=(("created_at", "created_at"), ("action", "action")),
    )

    class Meta:
        model = AuditLog
        fields = []

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(actor_email__icontains=value)
            | Q(description__icontains=value)
            | Q(reason__icontains=value)
        )
