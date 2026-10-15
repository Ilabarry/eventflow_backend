"""
Filtres django-filter pour la liste des événements.

Permet de filtrer via des paramètres URL :
    ?category=<uuid>
    ?format=ONLINE
    ?participation_type=PAID
    ?status=PUBLISHED
    ?city=Dakar
    ?start_date=2026-10-01
    ?end_date=2026-12-31
    ?upcoming=true
    ?search=tech
    ?ordering=-start_at
"""

import django_filters
from django.utils import timezone

from apps.events.constants import (
    ALLOWED_ORDERING_FIELDS,
    CapacityType,
    EventFormat,
    EventStatus,
    ParticipationType,
)
from apps.events.models import Event


class EventFilter(django_filters.FilterSet):
    """Filtre pour les événements."""

    # ------------------------------------------------------------------
    # Filtres sur champs simples
    # ------------------------------------------------------------------
    category = django_filters.UUIDFilter(field_name="category__id")
    format = django_filters.ChoiceFilter(choices=EventFormat.choices)
    participation_type = django_filters.ChoiceFilter(choices=ParticipationType.choices)
    capacity_type = django_filters.ChoiceFilter(choices=CapacityType.choices)
    status = django_filters.ChoiceFilter(choices=EventStatus.choices)
    city = django_filters.CharFilter(field_name="city", lookup_expr="iexact")
    organizer = django_filters.UUIDFilter(field_name="organizer__id")

    # ------------------------------------------------------------------
    # Filtres sur dates
    # ------------------------------------------------------------------
    start_date = django_filters.DateFilter(
        field_name="start_at",
        lookup_expr="date__gte",
        help_text="Événements commençant après cette date (YYYY-MM-DD).",
    )
    end_date = django_filters.DateFilter(
        field_name="start_at",
        lookup_expr="date__lte",
        help_text="Événements commençant avant cette date (YYYY-MM-DD).",
    )

    # ------------------------------------------------------------------
    # Filtres booléens (upcoming / past)
    # ------------------------------------------------------------------
    upcoming = django_filters.BooleanFilter(
        method="filter_upcoming",
        help_text="Si true, uniquement les événements à venir.",
    )
    past = django_filters.BooleanFilter(
        method="filter_past",
        help_text="Si true, uniquement les événements passés.",
    )

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Recherche dans le titre, la description courte et la ville.",
    )

    # ------------------------------------------------------------------
    # Tri
    # ------------------------------------------------------------------
    ordering = django_filters.OrderingFilter(
        fields=tuple(
            (field.lstrip("-"), field.lstrip("-"))
            for field in ALLOWED_ORDERING_FIELDS
        ),
        help_text="Champs de tri autorisés.",
    )

    class Meta:
        model = Event
        fields = [
            "category",
            "format",
            "participation_type",
            "capacity_type",
            "status",
            "city",
            "organizer",
        ]

    # ------------------------------------------------------------------
    # Méthodes de filtrage personnalisées
    # ------------------------------------------------------------------
    def filter_upcoming(self, queryset, name, value):
        """Filtre les événements à venir (start_at dans le futur)."""
        if value:
            return queryset.filter(start_at__gte=timezone.now())
        return queryset

    def filter_past(self, queryset, name, value):
        """Filtre les événements passés (end_at dans le passé)."""
        if value:
            return queryset.filter(end_at__lt=timezone.now())
        return queryset

    def filter_search(self, queryset, name, value):
        """
        Recherche insensible à la casse dans plusieurs champs.

        Note : on utilise __icontains (LIKE %...%) qui est performant
        sur de petites bases. Pour de grosses bases, envisager
        PostgreSQL full-text search (SearchVector).
        """
        if value:
            from django.db.models import Q

            return queryset.filter(
                Q(title__icontains=value)
                | Q(short_description__icontains=value)
                | Q(city__icontains=value)
            )
        return queryset