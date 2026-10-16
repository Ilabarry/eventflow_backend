"""
Tests de la phase 4 : liste d'accueil et statistiques d'un événement.

Lancer :
    python manage.py test apps.attendance
"""

import uuid

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.attendance.selectors import get_event_attendance_stats
from apps.attendance.tests import FAST_HASHER, AttendanceTestDataMixin
from apps.registrations.constants import RegistrationStatus


def list_url(event_id):
    return f"/api/events/{event_id}/attendance/"


def stats_url(event_id):
    return f"/api/events/{event_id}/attendance/stats/"


class EventAttendanceDataMixin(AttendanceTestDataMixin):
    """
    Ajoute à l'événement de base un jeu de données réaliste :
        - Awa      : PRESENT (MANUAL)   ← inscription de base
        - Koffi    : PRESENT (QR_CODE)
        - Sena     : ABSENT
        - Yao      : pas encore arrivé
        - Annulé   : inscription CANCELLED  (exclue des stats)
        - Attente  : inscription PENDING    (exclue des stats)
    """

    def mark(self, registration, status, method=None):
        return Attendance.objects.create(
            registration=registration,
            status=status,
            checked_in_at=timezone.now() if status == AttendanceStatus.PRESENT else None,
            check_in_method=method,
            recorded_by=self.organizer,
        )

    def setUp(self):
        super().setUp()
        self.koffi = self.make_user("koffi@test.com")
        self.sena = self.make_user("sena@test.com")
        self.yao = self.make_user("yao@test.com")
        cancelled_user = self.make_user("annule@test.com")
        pending_user = self.make_user("attente@test.com")

        self.reg_koffi = self.make_registration(self.koffi, self.event)
        self.reg_sena = self.make_registration(self.sena, self.event)
        self.reg_yao = self.make_registration(self.yao, self.event)
        self.make_registration(cancelled_user, self.event, status=RegistrationStatus.CANCELLED)
        self.make_registration(pending_user, self.event, status=RegistrationStatus.PENDING)

        self.mark(self.registration, AttendanceStatus.PRESENT, CheckInMethod.MANUAL)
        self.mark(self.reg_koffi, AttendanceStatus.PRESENT, CheckInMethod.QR_CODE)
        self.mark(self.reg_sena, AttendanceStatus.ABSENT)


# ==================================================================
# STATISTIQUES (selector)
# ==================================================================
@FAST_HASHER
class AttendanceStatsTests(AttendanceTestDataMixin, TestCase):

    def test_zero_participant(self):
        event = self.make_event(self.organizer, self.category)
        stats = get_event_attendance_stats(event)
        self.assertEqual(stats["total_registered"], 0)
        self.assertEqual(stats["attendance_rate"], 0.0)  # pas de division par zéro
        self.assertEqual(stats["check_ins_by_hour"], [])

    def test_one_participant_not_arrived(self):
        stats = get_event_attendance_stats(self.event)
        self.assertEqual(stats["total_registered"], 1)
        self.assertEqual(stats["not_checked_in"], 1)
        self.assertEqual(stats["attendance_rate"], 0.0)

    def test_one_participant_present_is_100_percent(self):
        Attendance.objects.create(
            registration=self.registration, status=AttendanceStatus.PRESENT,
            checked_in_at=timezone.now(), check_in_method=CheckInMethod.MANUAL,
        )
        stats = get_event_attendance_stats(self.event)
        self.assertEqual(stats["present"], 1)
        self.assertEqual(stats["attendance_rate"], 100.0)


@FAST_HASHER
class AttendanceStatsPartialTests(EventAttendanceDataMixin, TestCase):

    def test_partial_attendance(self):
        stats = get_event_attendance_stats(self.event)
        # 4 confirmés (annulé et en attente exclus)
        self.assertEqual(stats["total_registered"], 4)
        self.assertEqual(stats["present"], 2)
        self.assertEqual(stats["absent"], 1)
        self.assertEqual(stats["not_checked_in"], 1)
        self.assertEqual(stats["attendance_rate"], 50.0)
        self.assertEqual(stats["manual_check_ins"], 1)
        self.assertEqual(stats["qr_check_ins"], 1)
        self.assertEqual(sum(row["count"] for row in stats["check_ins_by_hour"]), 2)

    def test_counts_always_add_up(self):
        stats = get_event_attendance_stats(self.event)
        self.assertEqual(
            stats["present"] + stats["absent"] + stats["not_checked_in"],
            stats["total_registered"],
        )


# ==================================================================
# API : liste d'accueil
# ==================================================================
@FAST_HASHER
class EventAttendanceListApiTests(EventAttendanceDataMixin, APITestCase):

    def get_list(self, user=None, **params):
        self.client.force_authenticate(user=user or self.organizer)
        return self.client.get(list_url(self.event.id), params)

    def test_organizer_sees_all_confirmed_registrations(self):
        response = self.get_list()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 4)
        statuses = sorted(row["attendance_status"] for row in data["results"])
        self.assertEqual(statuses, ["ABSENT", "NOT_CHECKED_IN", "PRESENT", "PRESENT"])

    def test_filter_present(self):
        self.assertEqual(self.get_list(status="PRESENT").json()["data"]["count"], 2)

    def test_filter_not_checked_in(self):
        results = self.get_list(status="NOT_CHECKED_IN").json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["participant_email"], "yao@test.com")
        self.assertIsNone(results[0]["attendance_id"])

    def test_filter_by_method(self):
        results = self.get_list(method="QR_CODE").json()["data"]["results"]
        self.assertEqual([r["participant_email"] for r in results], ["koffi@test.com"])

    def test_search_by_email(self):
        results = self.get_list(search="sena@").json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["attendance_status"], "ABSENT")

    def test_search_by_reference(self):
        results = self.get_list(search=self.reg_yao.reference).json()["data"]["results"]
        self.assertEqual(results[0]["registration_id"], str(self.reg_yao.id))

    def test_invalid_status_returns_400(self):
        response = self.get_list(status="HACK")
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.json()["errors"])

    def test_invalid_ordering_returns_400(self):
        """Seuls les champs de tri de la liste blanche sont acceptés."""
        self.assertEqual(self.get_list(ordering="participant__password").status_code, 400)

    def test_ordering_by_checked_in_at(self):
        response = self.get_list(ordering="checked_in_at", status="PRESENT")
        self.assertEqual(response.status_code, 200)

    def test_participant_is_forbidden(self):
        self.assertEqual(self.get_list(user=self.participant).status_code, 403)

    def test_other_organizer_is_forbidden(self):
        self.assertEqual(self.get_list(user=self.other_organizer).status_code, 403)

    def test_admin_is_allowed(self):
        self.assertEqual(self.get_list(user=self.admin).status_code, 200)

    def test_unknown_event_returns_404(self):
        self.client.force_authenticate(user=self.organizer)
        self.assertEqual(self.client.get(list_url(uuid.uuid4())).status_code, 404)

    def test_anonymous_returns_401(self):
        self.assertEqual(self.client.get(list_url(self.event.id)).status_code, 401)

    def test_no_n_plus_one_queries(self):
        """Le nombre de requêtes SQL ne dépend pas du nombre de participants."""
        self.client.force_authenticate(user=self.organizer)
        with CaptureQueriesContext(connection) as small:
            self.client.get(list_url(self.event.id))
        for i in range(5):
            self.make_registration(self.make_user(f"extra{i}@test.com"), self.event)
        with CaptureQueriesContext(connection) as large:
            self.client.get(list_url(self.event.id))
        self.assertEqual(len(small), len(large))


# ==================================================================
# API : statistiques
# ==================================================================
@FAST_HASHER
class EventAttendanceStatsApiTests(EventAttendanceDataMixin, APITestCase):

    def test_organizer_gets_stats(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.get(stats_url(self.event.id))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_registered"], 4)
        self.assertEqual(data["attendance_rate"], 50.0)

    def test_participant_is_forbidden(self):
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.get(stats_url(self.event.id)).status_code, 403)
