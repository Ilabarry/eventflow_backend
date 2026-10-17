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