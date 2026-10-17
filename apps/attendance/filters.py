"""
Filtres de la liste d'accueil d'un événement (organisateur).

La liste porte sur les INSCRIPTIONS confirmées de l'événement, chacune
accompagnée de sa fiche de présence éventuelle. Cela permet d'afficher
aussi les participants pas encore arrivés (NOT_CHECKED_IN).

Paramètres d'URL disponibles :
    ?search=awa                  nom, prénom, e-mail ou référence d'inscription
    ?status=PRESENT              PRESENT | ABSENT | NOT_CHECKED_IN
    ?method=MANUAL               MANUAL | QR_CODE
    ?checked_in_after=...        date/heure ISO 8601
    ?checked_in_before=...       date/heure ISO 8601
    ?ordering=-checked_in_at     voir ORDERING_FIELDS ci-dessous
"""

import django_filters
from django.db.models import Q

from apps.attendance.constants import (
    NOT_CHECKED_IN,
    AttendanceStatus,
    CheckInMethod,
)
from apps.registrations.models import Registration

STATUS_FILTER_CHOICES = (
    (AttendanceStatus.PRESENT, "Présent"),
    (AttendanceStatus.ABSENT, "Absent"),
    (NOT_CHECKED_IN, "Pas encore arrivé"),
)


class EventAttendanceFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    status = django_filters.ChoiceFilter(
        choices=STATUS_FILTER_CHOICES, method="filter_status",
    )
    method = django_filters.ChoiceFilter(
        choices=CheckInMethod.choices, field_name="attendance__check_in_method",
    )
    checked_in_after = django_filters.IsoDateTimeFilter(
        field_name="attendance__checked_in_at", lookup_expr="gte",
    )
    checked_in_before = django_filters.IsoDateTimeFilter(
        field_name="attendance__checked_in_at", lookup_expr="lte",
    )
    # Liste blanche des tris autorisés : un champ arbitraire dans
    # ?ordering= serait refusé (400) au lieu d'être passé à la base.
    ordering = django_filters.OrderingFilter(
        fields=(
            ("participant__last_name", "last_name"),
            ("participant__first_name", "first_name"),
            ("attendance__checked_in_at", "checked_in_at"),
            ("registered_at", "registered_at"),
        ),
    )

    class Meta:
        model = Registration
        fields = []

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(participant__first_name__icontains=value)
            | Q(participant__last_name__icontains=value)
            | Q(participant__email__icontains=value)
            | Q(reference__icontains=value)
        )

    def filter_status(self, queryset, name, value):
        if value == NOT_CHECKED_IN:
            # Pas de fiche de présence du tout
            return queryset.filter(attendance__isnull=True)
        return queryset.filter(attendance__status=value)
