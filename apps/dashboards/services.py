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