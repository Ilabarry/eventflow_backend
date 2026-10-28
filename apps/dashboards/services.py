"""Services de composition des données des dashboards EVENTFLOW."""

from apps.dashboards.selectors import (
    ADMIN_RECENT_EVENTS_LIMIT,
    ADMIN_RECENT_USERS_LIMIT,
    PARTICIPANT_RECENT_REGISTRATIONS_LIMIT,
    PARTICIPANT_UPCOMING_LIMIT,
    RECENT_REGISTRATIONS_LIMIT,
    UPCOMING_EVENTS_LIMIT,
    get_admin_attendance_summary,
    get_admin_event_summary,
    get_admin_recent_events,
    get_admin_recent_users,
    get_admin_registration_summary,
    get_admin_user_summary,
    get_organizer_event_summary,
    get_organizer_registration_summary,
    get_organizer_upcoming_events,
    get_participant_summary,
    get_participant_upcoming_registrations,
    get_recent_organizer_registrations,
    get_recent_participant_registrations,
)

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.dashboards.statistics import (
    get_admin_statistics as select_admin_statistics,
    get_organizer_statistics as select_organizer_statistics,
)

class OrganizerDashboardService:
    """Assemble les données du dashboard d'un organisateur."""

    @staticmethod
    def get_dashboard(*, user) -> dict:
        summary = {
            **get_organizer_event_summary(user=user),
            **get_organizer_registration_summary(user=user),
        }

        return {
            "summary": summary,
            "upcoming_events": get_organizer_upcoming_events(
                user=user,
                limit=UPCOMING_EVENTS_LIMIT,
            ),
            "recent_registrations": get_recent_organizer_registrations(
                user=user,
                limit=RECENT_REGISTRATIONS_LIMIT,
            ),
            "payment_statistics_available": False,
            "financial_statistics": None,
        }


class ParticipantDashboardService:
    """Assemble les données personnelles du participant connecté."""

    @staticmethod
    def get_dashboard(*, user) -> dict:
        return {
            "summary": get_participant_summary(user=user),
            "upcoming_registrations": get_participant_upcoming_registrations(
                user=user,
                limit=PARTICIPANT_UPCOMING_LIMIT,
            ),
            "recent_registrations": get_recent_participant_registrations(
                user=user,
                limit=PARTICIPANT_RECENT_REGISTRATIONS_LIMIT,
            ),
            "availability": {
                "tickets": False,
                "certificates": False,
                "notifications": False,
                "payments": False,
            },
            "tickets": None,
            "certificates": None,
            "unread_notifications": None,
            "recent_notifications": None,
        }


class AdminDashboardService:
    """Assemble les indicateurs globaux réservés à l'administrateur."""

    @staticmethod
    def get_dashboard() -> dict:
        attendance = get_admin_attendance_summary()

        summary = {
            **get_admin_user_summary(),
            **get_admin_event_summary(),
            **get_admin_registration_summary(),
            "attended_registrations": attendance["attended_registrations"],
            "attendance_rate": attendance["attendance_rate"],
        }

        return {
            "summary": summary,
            "recent_events": get_admin_recent_events(
                limit=ADMIN_RECENT_EVENTS_LIMIT,
            ),
            "recent_users": get_admin_recent_users(
                limit=ADMIN_RECENT_USERS_LIMIT,
            ),
            "availability": {
                "tickets": False,
                "payments": False,
                "certificates": False,
                "notifications": False,
                "supervision_alerts": False,
            },
            "payment_statistics_available": False,
            "financial_statistics": None,
            "alerts": None,
        }
def _resolve_statistics_period(filters: dict):
    """Convertit les filtres de dates en bornes timezone-aware."""
    today = timezone.localdate()
    period = filters.get("period")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    if period == "today":
        start_date = end_date = today
    elif period == "last_7_days":
        start_date = today - timedelta(days=6)
        end_date = today
    elif period == "last_30_days":
        start_date = today - timedelta(days=29)
        end_date = today
    elif period == "last_12_months":
        month_index = today.year * 12 + today.month - 1 - 11
        year, month_zero_based = divmod(month_index, 12)
        start_date = date(year, month_zero_based + 1, 1)
        end_date = today
    elif not (start_date and end_date):
        # Valeur par défaut pour les statistiques organisateur.
        start_date = today - timedelta(days=29)
        end_date = today

    granularity = (
        "month"
        if period == "last_12_months"
        or (end_date - start_date).days > 90
        else "day"
    )

    current_timezone = timezone.get_current_timezone()
    start_at = timezone.make_aware(
        datetime.combine(start_date, time.min),
        current_timezone,
    )
    end_at_exclusive = timezone.make_aware(
        datetime.combine(end_date + timedelta(days=1), time.min),
        current_timezone,
    )

    period_info = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "granularity": granularity,
        "timezone": timezone.get_current_timezone_name(),
    }

    return start_at, end_at_exclusive, granularity, period_info


class DashboardStatisticsService:
    """Compose les statistiques graphiques des dashboards."""

    @staticmethod
    def get_organizer_statistics(*, user, filters: dict) -> dict:
        start_at, end_at_exclusive, granularity, period_info = (
            _resolve_statistics_period(filters)
        )

        statistics = select_organizer_statistics(
            user=user,
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
            event_id=filters.get("event_id"),
            event_status=filters.get("event_status"),
            event_format=filters.get("event_format"),
            registration_status=filters.get("registration_status"),
        )

        return {
            "period": period_info,
            **statistics,
            "payment_statistics_available": False,
            "financial_statistics": None,
        }

    @staticmethod
    def get_admin_statistics(*, filters: dict) -> dict:
        start_at, end_at_exclusive, granularity, period_info = (
            _resolve_statistics_period(filters)
        )

        statistics = select_admin_statistics(
            start_at=start_at,
            end_at_exclusive=end_at_exclusive,
            granularity=granularity,
        )

        return {
            "period": period_info,
            **statistics,
            "payment_statistics_available": False,
            "financial_statistics": None,
        }


# ==================================================================
# SERVICE : Dashboard admin « supervision »
# ==================================================================

class SupervisionDashboardService:
    """
    Compose les données du dashboard de supervision admin :
    KPIs avec tendance, éléments à traiter, activité journalière
    et événements récents.
    """

    @staticmethod
    def _trend(current: int, previous: int) -> float | None:
        """Calcule la tendance en % entre deux périodes."""
        if previous == 0:
            return None if current == 0 else 100.0
        return round(((current - previous) / previous) * 100, 1)

    @staticmethod
    def get_dashboard(*, days: int = 30) -> dict:
        from django.utils import timezone
        from django.db.models import Count

        from apps.accounts.models import User
        from apps.events.models import Event
        from apps.events.constants import EventStatus
        from apps.registrations.models import Registration

        now = timezone.now()
        today = timezone.localdate()

        # ── Bornes des périodes (courante et précédente)
        start_current = now - timedelta(days=days)
        start_previous = start_current - timedelta(days=days)

        # ── KPIs
        def count_users(start, end, role=None):
            qs = User.objects.filter(created_at__gte=start, created_at__lt=end)
            if role:
                qs = qs.filter(roles__name=role).distinct()
            return qs.count()

        def count_events(start, end, status=None):
            qs = Event.objects.filter(created_at__gte=start, created_at__lt=end)
            if status:
                qs = qs.filter(status=status)
            return qs.count()

        def count_registrations(start, end):
            return Registration.objects.filter(
                registered_at__gte=start, registered_at__lt=end
            ).count()

        users_cur = count_users(start_current, now)
        users_prev = count_users(start_previous, start_current)

        organizers_cur = count_users(start_current, now, role="organisateur")
        organizers_prev = count_users(start_previous, start_current, role="organisateur")

        events_cur = count_events(start_current, now)
        events_prev = count_events(start_previous, start_current)

        published_cur = count_events(start_current, now, status=EventStatus.PUBLISHED)
        published_prev = count_events(start_previous, start_current, status=EventStatus.PUBLISHED)

        registrations_cur = count_registrations(start_current, now)
        registrations_prev = count_registrations(start_previous, start_current)

        # ── À traiter
        pending_organizers = User.objects.filter(
            roles__name="organisateur",
            is_active=False,
        ).distinct().count()

        pending_events = Event.objects.filter(
            status=EventStatus.DRAFT,
        ).count()  # ajustez selon votre logique (DRAFT ≈ en attente de modération)

        suspended_accounts = User.objects.filter(is_active=False).count()
        reports = 0  # à brancher quand un modèle Report existera

        # ── Activité journalière
        activity = []
        for i in range(days):
            day = today - timedelta(days=days - 1 - i)
            day_start = timezone.make_aware(datetime.combine(day, time.min))
            day_end = day_start + timedelta(days=1)
            activity.append({
                "date": day.isoformat(),
                "registrations": count_registrations(day_start, day_end),
                "events": count_events(day_start, day_end),
                "users": count_users(day_start, day_end),
            })

        # ── Événements récents (5 derniers créés)
        recent_events = list(
            Event.objects.select_related("organizer")
            .order_by("-created_at")[:5]
        )

        return {
            "generated_at": now.isoformat(),
            "kpis": {
                "users": {
                    "value": users_cur,
                    "trend": SupervisionDashboardService._trend(users_cur, users_prev),
                },
                "organizers": {
                    "value": organizers_cur,
                    "trend": SupervisionDashboardService._trend(organizers_cur, organizers_prev),
                },
                "events": {
                    "value": events_cur,
                    "trend": SupervisionDashboardService._trend(events_cur, events_prev),
                },
                "published_events": {
                    "value": published_cur,
                    "trend": SupervisionDashboardService._trend(published_cur, published_prev),
                },
                "registrations": {
                    "value": registrations_cur,
                    "trend": SupervisionDashboardService._trend(registrations_cur, registrations_prev),
                },
            },
            "to_review": {
                "pending_organizers": pending_organizers,
                "pending_events": pending_events,
                "reports": reports,
                "suspended_accounts": suspended_accounts,
            },
            "activity": activity,
            "recent_events": recent_events,
        }