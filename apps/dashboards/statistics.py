"""Agrégations temporelles des dashboards EVENTFLOW."""

from django.contrib.auth import get_user_model
from django.db.models import Count, F
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from apps.events.models import Event
from apps.registrations.models import Registration


def _count_by_period(
    queryset,
    *,
    date_field: str,
    start_at,
    end_at_exclusive,
    granularity: str,
) -> list[dict]:
    """Compte les objets par jour ou par mois, directement en base."""
    current_timezone = timezone.get_current_timezone()

    if granularity == "month":
        period_expression = TruncMonth(
            date_field,
            tzinfo=current_timezone,
        )
    else:
        period_expression = TruncDate(
            date_field,
            tzinfo=current_timezone,
        )

    rows = (
        queryset
        .filter(**{
            f"{date_field}__gte": start_at,
            f"{date_field}__lt": end_at_exclusive,
        })
        .annotate(period=period_expression)
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    )

    points = []
    for row in rows:
        bucket = row["period"]
        label = (
            bucket.strftime("%Y-%m")
            if granularity == "month"
            else bucket.isoformat()
        )
        points.append({"period": label, "count": row["count"]})

    return points


def get_organizer_statistics(
    *,
    user,
    start_at,
    end_at_exclusive,
    granularity: str,
    event_id=None,
    event_status=None,
    event_format=None,
    registration_status=None,
) -> dict:
    """
    Statistiques limitées aux événements de l'organisateur.

    Les tendances d'événements utilisent created_at ;
    celles des inscriptions utilisent registered_at.
    """
    events = Event.objects.filter(organizer=user)
    registrations = Registration.objects.filter(event__organizer=user)

    if event_id:
        # Le filtre reste toujours à l'intérieur du périmètre de l'organisateur.
        events = events.filter(id=event_id)
        registrations = registrations.filter(event_id=event_id)

    if event_status:
        events = events.filter(status=event_status)
        registrations = registrations.filter(event__status=event_status)

    if event_format:
        events = events.filter(format=event_format)
        registrations = registrations.filter(event__format=event_format)

    if registration_status:
        registrations = registrations.filter(status=registration_status)

    event_period = events.filter(
        created_at__gte=start_at,
        created_at__lt=end_at_exclusive,
    )
    registration_period = registrations.filter(
        registered_at__gte=start_at,
        registered_at__lt=end_at_exclusive,
    )

    return {
        "events_created_over_time": _count_by_period(
            events,
            date_field="created_at",
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
        ),
        "registrations_over_time": _count_by_period(
            registrations,
            date_field="registered_at",
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
        ),
        "events_by_status": list(
            event_period
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        ),
        "events_by_format": list(
            event_period
            .values("format")
            .annotate(count=Count("id"))
            .order_by("format")
        ),
        "registrations_by_status": list(
            registration_period
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        ),
    }


def get_admin_statistics(
    *,
    start_at,
    end_at_exclusive,
    granularity: str,
) -> dict:
    """Statistiques temporelles globales, réservées à la vue admin."""
    user_model = get_user_model()
    users = user_model.objects.all()
    events = Event.objects.all()
    registrations = Registration.objects.all()

    user_period = users.filter(
        created_at__gte=start_at,
        created_at__lt=end_at_exclusive,
    )
    event_period = events.filter(
        created_at__gte=start_at,
        created_at__lt=end_at_exclusive,
    )
    registration_period = registrations.filter(
        registered_at__gte=start_at,
        registered_at__lt=end_at_exclusive,
    )

    users_by_role = (
        users
        .annotate(role=F("roles__name"))
        .filter(role__isnull=False)
        .values("role")
        .annotate(count=Count("id", distinct=True))
        .order_by("role")
    )

    return {
        "users_created_over_time": _count_by_period(
            users,
            date_field="created_at",
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
        ),
        "events_created_over_time": _count_by_period(
            events,
            date_field="created_at",
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
        ),
        "registrations_over_time": _count_by_period(
            registrations,
            date_field="registered_at",
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
        ),
        "events_by_status": list(
            event_period
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        ),
        "events_by_format": list(
            event_period
            .values("format")
            .annotate(count=Count("id"))
            .order_by("format")
        ),
        "registrations_by_status": list(
            registration_period
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        ),
        "users_by_role": list(users_by_role),
    }