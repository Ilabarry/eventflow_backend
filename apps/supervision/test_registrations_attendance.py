"""
Tests de la phase S4 : inscriptions et présences (lecture seule).

Lancer :
    python manage.py test apps.supervision
"""

import uuid
from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.attendance.tests import AttendanceTestDataMixin
from apps.events.models import Category
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.supervision.test_security import FAST_HASHER, SupervisionUsersMixin

REGISTRATIONS_URL = "/api/supervision/registrations/"
ATTENDANCE_URL = "/api/supervision/attendance/"

make_event = AttendanceTestDataMixin.make_event
make_registration = AttendanceTestDataMixin.make_registration


class RegistrationDataMixin(SupervisionUsersMixin):
    """
    Deux événements et quatre inscriptions :
        - participant → event_a : CONFIRMED, PRESENT (manuel)
        - organizer   → event_a : CONFIRMED, pas encore arrivé
        - role_admin  → event_a : PENDING
        - participant → event_b : CANCELLED
    """

    def setUp(self):
        super().setUp()
        category = Category.objects.create(name="Tech")
        self.event_a = make_event(self.organizer, category)
        self.event_b = make_event(self.organizer, category, starts_in=timedelta(days=4))
        self.present = make_registration(self.participant, self.event_a)
        self.waiting = make_registration(self.organizer, self.event_a)
        self.pending = make_registration(self.role_admin, self.event_a, status=RegistrationStatus.PENDING)
        self.cancelled = make_registration(self.participant, self.event_b, status=RegistrationStatus.CANCELLED)
        self.attendance = Attendance.objects.create(
            registration=self.present,
            status=AttendanceStatus.PRESENT,
            checked_in_at=self.event_a.start_at,
            check_in_method=CheckInMethod.MANUAL,
            recorded_by=self.organizer,
        )
        self.client.force_authenticate(user=self.role_admin)


# ==================================================================
# INSCRIPTIONS
# ==================================================================
@FAST_HASHER
class SupervisionRegistrationApiTests(RegistrationDataMixin, APITestCase):

    def rows(self, **params):
        return {r["id"]: r for r in self.client.get(REGISTRATIONS_URL, params).json()["data"]["results"]}

    def test_admin_sees_all_registrations(self):
        self.assertEqual(self.client.get(REGISTRATIONS_URL).json()["data"]["count"], 4)

    def test_attendance_status_per_case(self):
        rows = self.rows()
        self.assertEqual(rows[str(self.present.id)]["attendance_status"], "PRESENT")
        self.assertEqual(rows[str(self.waiting.id)]["attendance_status"], "NOT_CHECKED_IN")
        self.assertIsNone(rows[str(self.pending.id)]["attendance_status"])
        self.assertIsNone(rows[str(self.cancelled.id)]["attendance_status"])

    def test_filter_by_status(self):
        self.assertEqual(list(self.rows(status="CANCELLED")), [str(self.cancelled.id)])

    def test_filter_by_event(self):
        self.assertEqual(len(self.rows(event=str(self.event_a.id))), 3)

    def test_filter_by_participant(self):
        self.assertEqual(len(self.rows(participant=str(self.participant.id))), 2)

    def test_search_by_reference(self):
        self.assertEqual(list(self.rows(search=self.pending.reference)), [str(self.pending.id)])

    def test_invalid_status_returns_400(self):
        self.assertEqual(self.client.get(REGISTRATIONS_URL, {"status": "PAID"}).status_code, 400)

    def test_invalid_uuid_returns_400(self):
        self.assertEqual(self.client.get(REGISTRATIONS_URL, {"event": "pas-un-uuid"}).status_code, 400)

    def test_detail_with_attendance(self):
        data = self.client.get(f"{REGISTRATIONS_URL}{self.present.id}/").json()["data"]
        self.assertEqual(data["organizer_email"], "orga@test.com")
        self.assertEqual(data["attendance"]["status"], "PRESENT")
        self.assertEqual(data["attendance"]["recorded_by_email"], "orga@test.com")

    def test_detail_without_attendance(self):
        data = self.client.get(f"{REGISTRATIONS_URL}{self.waiting.id}/").json()["data"]
        self.assertIsNone(data["attendance"])

    def test_detail_unknown_returns_404(self):
        self.assertEqual(self.client.get(f"{REGISTRATIONS_URL}{uuid.uuid4()}/").status_code, 404)

    def test_read_only(self):
        """Aucune méthode d'écriture : l'admin ne modifie pas les inscriptions."""
        url = f"{REGISTRATIONS_URL}{self.pending.id}/"
        self.assertEqual(self.client.patch(url, {"status": "CONFIRMED"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(self.client.post(REGISTRATIONS_URL, {}, format="json").status_code, 405)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, RegistrationStatus.PENDING)

    def test_participant_is_forbidden(self):
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.get(REGISTRATIONS_URL).status_code, 403)

    def test_anonymous_returns_401(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(REGISTRATIONS_URL).status_code, 401)

    def test_no_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as small:
            self.client.get(REGISTRATIONS_URL)
        for i in range(5):
            make_registration(self.make_user(f"extra{i}@test.com"), self.event_b)
        with CaptureQueriesContext(connection) as large:
            self.client.get(REGISTRATIONS_URL)
        self.assertEqual(len(small), len(large))
        self.assertEqual(Registration.objects.count(), 9)


# ==================================================================
# PRÉSENCES
# ==================================================================
@FAST_HASHER
class SupervisionAttendanceApiTests(RegistrationDataMixin, APITestCase):

    def setUp(self):
        super().setUp()
        Attendance.objects.create(registration=self.waiting, status=AttendanceStatus.ABSENT)

    def get(self, **params):
        return self.client.get(ATTENDANCE_URL, params)

    def test_lists_all_attendance_records(self):
        self.assertEqual(self.get().json()["data"]["count"], 2)

    def test_row_content(self):
        row = self.get(status="PRESENT").json()["data"]["results"][0]
        self.assertEqual(row["participant_email"], "participant@test.com")
        self.assertEqual(row["recorded_by_email"], "orga@test.com")
        self.assertEqual(row["event_id"], str(self.event_a.id))

    def test_filter_by_status(self):
        self.assertEqual(self.get(status="ABSENT").json()["data"]["count"], 1)

    def test_filter_by_method(self):
        self.assertEqual(self.get(method="QR_CODE").json()["data"]["count"], 0)
        self.assertEqual(self.get(method="MANUAL").json()["data"]["count"], 1)

    def test_filter_by_event(self):
        self.assertEqual(self.get(event=str(self.event_b.id)).json()["data"]["count"], 0)

    def test_invalid_method_returns_400(self):
        self.assertEqual(self.get(method="FACE_ID").status_code, 400)

    def test_invalid_ordering_returns_400(self):
        self.assertEqual(self.get(ordering="registration__participant__password").status_code, 400)

    def test_organizer_is_forbidden(self):
        self.client.force_authenticate(user=self.organizer)
        self.assertEqual(self.get().status_code, 403)

    def test_no_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as small:
            self.get()
        for i in range(4):
            registration = make_registration(self.make_user(f"venu{i}@test.com"), self.event_b)
            Attendance.objects.create(
                registration=registration, status=AttendanceStatus.PRESENT,
                checked_in_at=self.event_b.start_at, check_in_method=CheckInMethod.MANUAL,
                recorded_by=self.organizer,
            )
        with CaptureQueriesContext(connection) as large:
            self.get()
        self.assertEqual(len(small), len(large))
