"""
Filtres des listes de supervision.

Phase S1 : journal d'audit.
    ?action=USER_SUSPENDED   ?entity_type=USER   ?entity_id=<uuid>
    ?actor=<uuid>            ?result=DENIED
    ?date_from=2026-10-01    ?date_to=2026-10-31   (dates incluses)
    ?search=awa              (e-mail de l'acteur, description, raison)
    ?ordering=-created_at    (liste blanche : created_at, action)

Phase S2 : utilisateurs et organisateurs (paramètres détaillés plus bas).
Phase S3 : événements et catégories (paramètres détaillés plus bas).
"""

import django_filters
from django.db.models import Q

from apps.accounts.constants import ALL_ROLES
from apps.accounts.models import User
from apps.events.constants import EventFormat, EventStatus
from apps.events.models import Category, Event
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


# ==================================================================
# UTILISATEURS (phase S2)
#   ?search=awa           (e-mail, prénom, nom, téléphone)
#   ?role=organisateur    (participant | organisateur | administrateur)
#   ?is_active=false      (comptes suspendus)
#   ?joined_from=2026-10-01  ?joined_to=2026-10-31
#   ?ordering=-created_at (liste blanche : created_at, last_name, email, last_login)
# ==================================================================
def _search_users(queryset, value):
    value = value.strip()
    if not value:
        return queryset
    return queryset.filter(
        Q(email__icontains=value)
        | Q(first_name__icontains=value)
        | Q(last_name__icontains=value)
        | Q(phone__icontains=value)
    )


class SupervisionUserFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    role = django_filters.ChoiceFilter(
        choices=[(role, role) for role in ALL_ROLES],
        method="filter_role",
    )
    is_active = django_filters.BooleanFilter()
    joined_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    joined_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    ordering = django_filters.OrderingFilter(
        fields=(
            ("created_at", "created_at"),
            ("last_name", "last_name"),
            ("email", "email"),
            ("last_login", "last_login"),
        ),
    )

    class Meta:
        model = User
        fields = []

    def filter_search(self, queryset, name, value):
        return _search_users(queryset, value)

    def filter_role(self, queryset, name, value):
        # Un rôle n'apparaît qu'une fois par compte : pas de doublons.
        return queryset.filter(roles__name=value)


# ==================================================================
# ORGANISATEURS (phase S2)
#   ?search=  ?is_active=
#   ?ordering=-events_total  (created_at, last_name, events_total,
#                             events_published, registrations_confirmed)
# ==================================================================
class OrganizerFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    is_active = django_filters.BooleanFilter()
    ordering = django_filters.OrderingFilter(
        fields=(
            ("created_at", "created_at"),
            ("last_name", "last_name"),
            ("events_total", "events_total"),
            ("events_published", "events_published"),
            ("registrations_confirmed", "registrations_confirmed"),
        ),
    )

    class Meta:
        model = User
        fields = []

    def filter_search(self, queryset, name, value):
        return _search_users(queryset, value)


# ==================================================================
# ÉVÉNEMENTS (phase S3)
#   ?search=          (titre, e-mail de l'organisateur)
#   ?status=CANCELLED ?format=ONLINE
#   ?organizer=<uuid> ?category=<uuid>   ?city=cotonou
#   ?starts_from=2026-11-01  ?starts_to=2026-11-30
#   ?ordering=-start_at  (start_at, created_at, title, registrations_confirmed)
# ==================================================================
class SupervisionEventFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    status = django_filters.ChoiceFilter(choices=EventStatus.choices)
    format = django_filters.ChoiceFilter(choices=EventFormat.choices)
    organizer = django_filters.UUIDFilter(field_name="organizer_id")
    category = django_filters.UUIDFilter(field_name="category_id")
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    starts_from = django_filters.DateFilter(field_name="start_at", lookup_expr="date__gte")
    starts_to = django_filters.DateFilter(field_name="start_at", lookup_expr="date__lte")
    ordering = django_filters.OrderingFilter(
        fields=(
            ("start_at", "start_at"),
            ("created_at", "created_at"),
            ("title", "title"),
            ("registrations_confirmed", "registrations_confirmed"),
        ),
    )

    class Meta:
        model = Event
        fields = []

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(Q(title__icontains=value) | Q(organizer__email__icontains=value))


# ==================================================================
# CATÉGORIES (phase S3)
#   ?search=tech  ?is_active=false
#   ?ordering=-events_total  (name, created_at, events_total)
# ==================================================================
class SupervisionCategoryFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()
    ordering = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("created_at", "created_at"),
            ("events_total", "events_total"),
        ),
    )

    class Meta:
        model = Category
        fields = []
