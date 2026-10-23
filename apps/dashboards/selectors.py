"""Requêtes en lecture pour les dashboards EVENTFLOW."""

from apps.dashboards.constants import (
    ADMIN_RECENT_EVENTS_LIMIT,
    ADMIN_RECENT_USERS_LIMIT,
    PARTICIPANT_RECENT_REGISTRATIONS_LIMIT,
    PARTICIPANT_UPCOMING_LIMIT,
    RECENT_REGISTRATIONS_LIMIT,
    UPCOMING_EVENTS_LIMIT,
)
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.events.constants import EventStatus
from apps.events.selectors import get_organizer_events
from apps.registrations.constants import ACTIVE_STATUSES, RegistrationStatus
from apps.registrations.models import Registration
from apps.attendance.constants import AttendanceStatus
from apps.registrations.selectors import get_user_registrations

from django.contrib.auth import get_user_model

from apps.accounts.constants import ROLE_ADMIN, ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.events.models import Event
from apps.events.selectors import get_all_events


def get_organizer_event_summary(*, user) -> dict[str, int]:
    """Compte les événements de cet organisateur, par statut."""
    now = timezone.now()

    return get_organizer_events(user).aggregate(
        total_events=Count("id"),
        published_events=Count(
            "id",
            filter=Q(status=EventStatus.PUBLISHED),
        ),
        upcoming_events=Count(
            "id",
            filter=Q(
                status=EventStatus.PUBLISHED,
                start_at__gte=now,
            ),
        ),
        completed_events=Count(
            "id",
            filter=Q(status=EventStatus.COMPLETED),
        ),
        draft_events=Count(
            "id",
            filter=Q(status=EventStatus.DRAFT),
        ),
        cancelled_events=Count(
            "id",
            filter=Q(status=EventStatus.CANCELLED),
        ),
    )


def get_organizer_registration_summary(*, user) -> dict[str, int]:
    """
    Compte les inscriptions aux événements de l'organisateur.
    total_registrations inclut aussi les inscriptions annulées.
    """
    registrations = Registration.objects.filter(event__organizer=user)

    return registrations.aggregate(
        total_registrations=Count("id"),
        active_registrations=Count(
            "id",
            filter=Q(status__in=ACTIVE_STATUSES),
        ),
        pending_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.PENDING),
        ),
        confirmed_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.CONFIRMED),
        ),
        cancelled_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.CANCELLED),
        ),
        active_unique_participants=Count(
            "participant",
            filter=Q(status__in=ACTIVE_STATUSES),
            distinct=True,
        ),
    )


def get_organizer_upcoming_events(
    *,
    user,
    limit: int = UPCOMING_EVENTS_LIMIT,
) -> QuerySet:
    """
    Retourne les prochains événements publiés de l'organisateur,
    avec les comptes d'inscriptions calculés en base.
    """
    now = timezone.now()

    return (
        get_organizer_events(user)
        .filter(
            status=EventStatus.PUBLISHED,
            start_at__gte=now,
        )
        .annotate(
            active_registrations_count=Count(
                "registrations",
                filter=Q(registrations__status__in=ACTIVE_STATUSES),
            ),
            pending_registrations_count=Count(
                "registrations",
                filter=Q(
                    registrations__status=RegistrationStatus.PENDING,
                ),
            ),
            confirmed_registrations_count=Count(
                "registrations",
                filter=Q(
                    registrations__status=RegistrationStatus.CONFIRMED,
                ),
            ),
        )
        .order_by("start_at")[:limit]
    )


def get_recent_organizer_registrations(
    *,
    user,
    limit: int = RECENT_REGISTRATIONS_LIMIT,
) -> QuerySet[Registration]:
    """Retourne les inscriptions récentes à ses propres événements."""
    return (
        Registration.objects
        .filter(event__organizer=user)
        .select_related("event", "participant")
        .order_by("-registered_at")[:limit]
    )


def get_participant_summary(*, user) -> dict[str, int]:
    """Compte les inscriptions et événements du participant connecté."""
    now = timezone.now()
    registrations = Registration.objects.filter(participant=user)

    return registrations.aggregate(
        total_registrations=Count("id"),
        pending_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.PENDING),
        ),
        confirmed_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.CONFIRMED),
        ),
        cancelled_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.CANCELLED),
        ),
        upcoming_events=Count(
            "event",
            filter=Q(
                status__in=ACTIVE_STATUSES,
                event__status=EventStatus.PUBLISHED,
                event__start_at__gte=now,
            ),
            distinct=True,
        ),
        completed_events=Count(
            "event",
            filter=Q(
                status=RegistrationStatus.CONFIRMED,
                event__status=EventStatus.COMPLETED,
            ),
            distinct=True,
        ),
        attended_events=Count(
            "event",
            filter=Q(
                status=RegistrationStatus.CONFIRMED,
                attendance__status=AttendanceStatus.PRESENT,
            ),
            distinct=True,
        ),
    )


def get_participant_upcoming_registrations(
    *,
    user,
    limit: int = PARTICIPANT_UPCOMING_LIMIT,
) -> QuerySet[Registration]:
    """Prochaines inscriptions actives, avec les événements publiés."""
    return (
        get_user_registrations(user)
        .filter(
            status__in=ACTIVE_STATUSES,
            event__status=EventStatus.PUBLISHED,
            event__start_at__gte=timezone.now(),
        )
        .order_by("event__start_at")[:limit]
    )


def get_recent_participant_registrations(
    *,
    user,
    limit: int = PARTICIPANT_RECENT_REGISTRATIONS_LIMIT,
) -> QuerySet[Registration]:
    """Dernières inscriptions personnelles du participant."""
    return get_user_registrations(user)[:limit]


def get_admin_user_summary() -> dict[str, int]:
    """Compte les utilisateurs actifs, inactifs et par rôle."""
    user_model = get_user_model()

    return user_model.objects.aggregate(
        total_users=Count("id", distinct=True),
        active_users=Count(
            "id",
            filter=Q(is_active=True),
            distinct=True,
        ),
        inactive_users=Count(
            "id",
            filter=Q(is_active=False),
            distinct=True,
        ),
        participant_users=Count(
            "id",
            filter=Q(roles__name=ROLE_PARTICIPANT),
            distinct=True,
        ),
        organizer_users=Count(
            "id",
            filter=Q(roles__name=ROLE_ORGANIZER),
            distinct=True,
        ),
        admin_users=Count(
            "id",
            filter=(
                Q(roles__name=ROLE_ADMIN)
                | Q(is_staff=True)
                | Q(is_superuser=True)
            ),
            distinct=True,
        ),
    )


def get_admin_event_summary() -> dict[str, int]:
    """Compte les événements de toute la plateforme, par statut."""
    now = timezone.now()

    return get_all_events().aggregate(
        total_events=Count("id"),
        published_events=Count(
            "id",
            filter=Q(status=EventStatus.PUBLISHED),
        ),
        upcoming_events=Count(
            "id",
            filter=Q(
                status=EventStatus.PUBLISHED,
                start_at__gte=now,
            ),
        ),
        completed_events=Count(
            "id",
            filter=Q(status=EventStatus.COMPLETED),
        ),
        draft_events=Count(
            "id",
            filter=Q(status=EventStatus.DRAFT),
        ),
        cancelled_events=Count(
            "id",
            filter=Q(status=EventStatus.CANCELLED),
        ),
    )


def get_admin_registration_summary() -> dict[str, int]:
    """Compte les inscriptions de toute la plateforme."""
    return Registration.objects.aggregate(
        total_registrations=Count("id"),
        active_registrations=Count(
            "id",
            filter=Q(status__in=ACTIVE_STATUSES),
        ),
        pending_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.PENDING),
        ),
        confirmed_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.CONFIRMED),
        ),
        cancelled_registrations=Count(
            "id",
            filter=Q(status=RegistrationStatus.CANCELLED),
        ),
        active_unique_participants=Count(
            "participant",
            filter=Q(status__in=ACTIVE_STATUSES),
            distinct=True,
        ),
    )


def get_admin_attendance_summary() -> dict[str, int | float]:
    """Compte les présences parmi les inscriptions confirmées."""
    counts = Registration.objects.filter(
        status=RegistrationStatus.CONFIRMED,
    ).aggregate(
        confirmed_registrations=Count("id"),
        attended_registrations=Count(
            "id",
            filter=Q(attendance__status=AttendanceStatus.PRESENT),
        ),
    )

    total_confirmed = counts["confirmed_registrations"]
    attended = counts["attended_registrations"]

    return {
        **counts,
        "attendance_rate": (
            round(attended / total_confirmed * 100, 1)
            if total_confirmed
            else 0.0
        ),
    }


def get_admin_recent_events(
    *,
    limit: int = ADMIN_RECENT_EVENTS_LIMIT,
) -> QuerySet[Event]:
    """Retourne les derniers événements créés sur la plateforme."""
    return get_all_events()[:limit]


def get_admin_recent_users(
    *,
    limit: int = ADMIN_RECENT_USERS_LIMIT,
) -> QuerySet:
    """Retourne les derniers utilisateurs créés, sans charger leurs inscriptions."""
    user_model = get_user_model()
    return user_model.objects.order_by("-created_at")[:limit]