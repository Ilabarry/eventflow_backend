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
    ?ordering=RANDOM
    ?ordering=RANDOM:12345   (seed optionnel, ordre stable par seed)
"""

import django_filters
from django.db import models
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
    # ⚠️ On définit `method=` pour intercepter RANDOM et valider contre
    # la liste blanche MANUELLEMENT. Comme `method=` remplace le
    # traitement natif d'OrderingFilter, on ne peut PAS déléguer à
    # `filter()` (récursion infinie). On réimplémente donc le tri ici.
    ordering = django_filters.OrderingFilter(
        fields=ALLOWED_ORDERING_FIELDS,
        method="filter_ordering",
        help_text=(
            "Champs de tri autorisés (préfixe '-' pour descendant). "
            "Utiliser 'RANDOM' pour un ordre aléatoire, "
            "ou 'RANDOM:<seed>' pour un ordre aléatoire stable."
        ),
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
            return queryset.filter(
                models.Q(title__icontains=value)
                | models.Q(short_description__icontains=value)
                | models.Q(city__icontains=value)
            )
        return queryset

    def filter_ordering(self, queryset, name, value):
        """
        Tri personnalisé.

        Contrat :
            - ``?ordering=RANDOM``         → aléatoire simple (order_by('?'))
            - ``?ordering=RANDOM:<seed>``  → aléatoire STABLE pour un seed donné
                                            (utile pour que la pagination reste
                                             cohérente entre les pages)
            - ``?ordering=field``          → tri croissant si `field` ∈ liste blanche
            - ``?ordering=-field``         → tri décroissant si `field` ∈ liste blanche
            - autre valeur                 → ignorée (on renvoie le queryset tel quel)

        ⚠️ On ne peut PAS appeler `OrderingFilter.filter()` ici : `method=` a
        remplacé son comportement, et déléguer à `filter()` provoquerait une
        récursion infinie.
        """
        if not value:
            return queryset

        # `value` peut être une chaîne ("-start_at") ou une liste
        # (OrderingFilter accepte plusieurs tri séparés par des virgules).
        raw_values = value if isinstance(value, (list, tuple)) else [value]

        # ----- Cas 1 : RANDOM / RANDOM:<seed> -----
        for raw in raw_values:
            raw_str = str(raw)
            upper = raw_str.upper()

            if upper == "RANDOM":
                # Aléatoire simple. Sur SQLite et PostgreSQL, `order_by('?')`
                # fonctionne. Sur de très grosses tables c'est lent mais
                # acceptable pour un MVP.
                return queryset.order_by("?")

            if upper.startswith("RANDOM:"):
                seed = raw_str.split(":", 1)[1] or "0"
                # Hash déterministe de (id + seed) : pour un même seed,
                # l'ordre est stable → la pagination reste cohérente.
                return queryset.annotate(
                    _rand=models.functions.MD5(
                        models.functions.Concat(
                            models.F("id"),
                            models.Value(seed),
                            output_field=models.TextField(),
                        )
                    )
                ).order_by("_rand")

        # ----- Cas 2 : tri standard, validé contre la liste blanche -----
        allowed = set(ALLOWED_ORDERING_FIELDS)
        ordering_fields = []
        for raw in raw_values:
            field = str(raw).lstrip("-")
            if field in allowed:
                # On conserve le "-" s'il était présent (tri descendant)
                ordering_fields.append(str(raw))

        if not ordering_fields:
            return queryset

        return queryset.order_by(*ordering_fields)