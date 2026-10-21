"""
Tests de la phase S6 : tableau de bord, statistiques et alertes.

Lancer :
    python manage.py test apps.supervision
"""

from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.attendance.tests import AttendanceTestDataMixin
from apps.events.constants import EventStatus
from apps.events.models import Category
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.supervision.constants import AuditAction, AuditEntity, AuditResult
from apps.supervision.services import AuditService
from apps.supervision.test_security import FAST_HASHER, SupervisionUsersMixin

DASHBOARD_URL = "/api/supervision/dashboard/"
STATISTICS_URL = "/api/supervision/statistics/"
ALERTS_URL = "/api/supervision/alerts/"

make_event = AttendanceTestDataMixin.make_event
make_registration = AttendanceTestDataMixin.make_registration


class PlatformDataMixin(SupervisionUsersMixin):
    """
    Données :
        - 5 comptes (participant, organisateur, 3 admins), dont aucun suspendu
        - catégories : Tech (2 événements), Sport (0, désactivée)
        - started   : publié, commencé il y a 1 h, à Cotonou
        - upcoming  : publié, dans 3 jours, à Porto-Novo, sans inscrit
        - inscriptions sur started : participant CONFIRMED + PRESENT,
                                     orga CONFIRMED (pas arrivé),
                                     admin PENDING
    """

    def setUp(self):
        super().setUp()
        tech = Category.objects.create(name="Tech")
        Category.objects.create(name="Sport", is_active=False)
        self.started = make_event(self.organizer, tech)
        self.upcoming = make_event(self.organizer, tech, starts_in=timedelta(days=3))
        self.upcoming.city = "Porto-Novo"
        self.upcoming.save()
        present = make_registration(self.participant, self.started)
        make_registration(self.organizer, self.started)
        self.pending = make_registration(self.role_admin, self.started, status=RegistrationStatus.PENDING)
        Attendance.objects.create(
            registration=present, status=AttendanceStatus.PRESENT,
            checked_in_at=timezone.now(), check_in_method=CheckInMethod.MANUAL,
        )
        self.client.force_authenticate(user=self.role_admin)


# ==================================================================
# TABLEAU DE BORD
# ==================================================================
@FAST_HASHER
class DashboardApiTests(PlatformDataMixin, APITestCase):

    def get_data(self):
        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_user_counters(self):
        users = self.get_data()["users"]
        self.assertEqual(users["total"], 5)
        self.assertEqual(users["suspended"], 0)
        self.assertEqual(users["participants"], 1)
        self.assertEqual(users["organizers"], 1)
        self.assertEqual(users["admins"], 3)
        self.assertEqual(users["new_last_30_days"], 5)

    def test_suspended_user_is_counted(self):
        self.participant.is_active = False
        self.participant.save()
        users = self.get_data()["users"]
        self.assertEqual((users["active"], users["suspended"]), (4, 1))

    def test_event_counters(self):
        events = self.get_data()["events"]
        self.assertEqual(events["total"], 2)
        self.assertEqual(events["published"], 2)
        self.assertEqual(events["upcoming"], 1)

    def test_registration_and_attendance_counters(self):
        data = self.get_data()
        self.assertEqual(data["registrations"]["confirmed"], 2)
        self.assertEqual(data["registrations"]["pending"], 1)
        self.assertEqual(data["attendance"]["present"], 1)
        self.assertEqual(data["attendance"]["expected"], 2)
        self.assertEqual(data["attendance"]["attendance_rate"], 50.0)

    def test_category_counters(self):
        self.assertEqual(self.get_data()["categories"], {"total": 2, "active": 1, "inactive": 1})

    def test_empty_platform_has_no_division_by_zero(self):
        # Les présences d'abord : Attendance protège ses inscriptions (PROTECT).
        Attendance.objects.all().delete()
        Registration.objects.all().delete()
        self.assertEqual(self.get_data()["attendance"]["attendance_rate"], 0.0)

    def test_query_count_does_not_grow_with_data(self):
        with CaptureQueriesContext(connection) as small:
            self.client.get(DASHBOARD_URL)
        for i in range(5):
            make_registration(self.make_user(f"extra{i}@test.com"), self.upcoming)
        with CaptureQueriesContext(connection) as large:
            self.client.get(DASHBOARD_URL)
        self.assertEqual(len(small), len(large))

    def test_participant_is_forbidden(self):
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.get(DASHBOARD_URL).status_code, 403)

    def test_anonymous_returns_401(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(DASHBOARD_URL).status_code, 401)


# ==================================================================
# STATISTIQUES
# ==================================================================
@FAST_HASHER
class StatisticsApiTests(PlatformDataMixin, APITestCase):

    def test_default_is_12_months_without_gaps(self):
        data = self.client.get(STATISTICS_URL).json()["data"]
        self.assertEqual(data["months"], 12)
        self.assertEqual(len(data["monthly"]), 12)
        current = timezone.localtime().strftime("%Y-%m")
        self.assertEqual(data["monthly"][-1]["month"], current)

    def test_current_month_values(self):
        last = self.client.get(STATISTICS_URL, {"months": 3}).json()["data"]["monthly"][-1]
        self.assertEqual(last["new_users"], 5)
        self.assertEqual(last["events_created"], 2)
        self.assertEqual(last["registrations"], 3)
        self.assertEqual(last["check_ins"], 1)

    def test_breakdowns(self):
        data = self.client.get(STATISTICS_URL).json()["data"]
        self.assertEqual([(c["name"], c["events"]) for c in data["events_by_category"]], [("Tech", 2)])
        self.assertEqual({c["city"] for c in data["events_by_city"]}, {"Cotonou", "Porto-Novo"})
        statuses = {r["status"]: r["total"] for r in data["registrations_by_status"]}
        self.assertEqual(statuses, {"CONFIRMED": 2, "PENDING": 1})

    def test_months_out_of_range_returns_400(self):
        self.assertEqual(self.client.get(STATISTICS_URL, {"months": 0}).status_code, 400)
        self.assertEqual(self.client.get(STATISTICS_URL, {"months": 99}).status_code, 400)

    def test_months_not_a_number_returns_400(self):
        response = self.client.get(STATISTICS_URL, {"months": "douze"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("months", response.json()["errors"])

    def test_organizer_is_forbidden(self):
        self.client.force_authenticate(user=self.organizer)
        self.assertEqual(self.client.get(STATISTICS_URL).status_code, 403)


# ==================================================================
# ALERTES
# ==================================================================
@FAST_HASHER
class AlertsApiTests(PlatformDataMixin, APITestCase):

    def alerts(self):
        response = self.client.get(ALERTS_URL)
        self.assertEqual(response.status_code, 200)
        return {a["code"]: a for a in response.json()["data"]}

    def test_upcoming_event_without_registration(self):
        alert = self.alerts()["UPCOMING_EVENTS_WITHOUT_REGISTRATIONS"]
        self.assertEqual(alert["count"], 1)
        self.assertEqual(alert["samples"][0]["id"], str(self.upcoming.id))

    def test_no_alert_when_nothing_to_report(self):
        codes = self.alerts()
        self.assertNotIn("SECURITY_DENIALS", codes)
        self.assertNotIn("SUSPENDED_ACCOUNTS", codes)
        self.assertNotIn("ENDED_EVENTS_STILL_PUBLISHED", codes)
        self.assertNotIn("STALE_PENDING_REGISTRATIONS", codes)

    def test_security_denials(self):
        AuditService.log(
            actor=self.role_admin, action=AuditAction.USER_SUSPENDED, entity_type=AuditEntity.USER,
            entity_id=self.role_admin.id, description="Tentative refusée", result=AuditResult.DENIED,
        )
        alert = self.alerts()["SECURITY_DENIALS"]
        self.assertEqual(alert["level"], "CRITICAL")
        self.assertEqual(alert["samples"][0]["actor_email"], "admin.role@test.com")

    def test_critical_alerts_come_first(self):
        AuditService.log(
            actor=self.role_admin, action=AuditAction.USER_SUSPENDED, entity_type=AuditEntity.USER,
            description="Tentative refusée", result=AuditResult.DENIED,
        )
        levels = [a["level"] for a in self.client.get(ALERTS_URL).json()["data"]]
        self.assertEqual(levels[0], "CRITICAL")

    def test_ended_event_still_published(self):
        make_event(self.organizer, self.started.category, starts_in=timedelta(days=-3))
        self.assertEqual(self.alerts()["ENDED_EVENTS_STILL_PUBLISHED"]["count"], 1)

    def test_stale_pending_registration(self):
        # registered_at est rempli automatiquement : on le recule avec update().
        Registration.objects.filter(pk=self.pending.pk).update(
            registered_at=timezone.now() - timedelta(days=10),
        )
        self.assertEqual(self.alerts()["STALE_PENDING_REGISTRATIONS"]["count"], 1)

    def test_suspended_accounts(self):
        self.participant.is_active = False
        self.participant.save()
        self.assertEqual(self.alerts()["SUSPENDED_ACCOUNTS"]["count"], 1)

    def test_cancelled_upcoming_event_is_not_an_alert(self):
        self.upcoming.status = EventStatus.CANCELLED
        self.upcoming.save()
        self.assertNotIn("UPCOMING_EVENTS_WITHOUT_REGISTRATIONS", self.alerts())

    def test_participant_is_forbidden(self):
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.get(ALERTS_URL).status_code, 403)
