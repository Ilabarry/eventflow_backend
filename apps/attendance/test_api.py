"""
Tests de l'API Attendance — phase 3.

On teste ce que verra Angular : codes HTTP, format standard
{success, message, data | errors}, authentification et permissions.

Lancer :
    python manage.py test apps.attendance
"""

import uuid

from rest_framework.test import APITestCase

from apps.attendance.models import Attendance
from apps.attendance.tests import FAST_HASHER, AttendanceTestDataMixin

CHECK_IN_URL = "/api/attendance/check-in/"
MARK_ABSENT_URL = "/api/attendance/mark-absent/"
ME_URL = "/api/attendance/me/"


def detail_url(attendance_id):
    return f"/api/attendance/{attendance_id}/"


def registration_attendance_url(registration_id):
    return f"/api/registrations/{registration_id}/attendance/"


@FAST_HASHER
class CheckInApiTests(AttendanceTestDataMixin, APITestCase):

    def post_check_in(self, user, registration_id=None):
        if user:
            self.client.force_authenticate(user=user)
        payload = {} if registration_id is None else {"registration_id": str(registration_id)}
        return self.client.post(CHECK_IN_URL, payload, format="json")

    # --- Cas nominal -------------------------------------------------
    def test_organizer_check_in_returns_201(self):
        response = self.post_check_in(self.organizer, self.registration.id)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["message"], "Présence enregistrée avec succès.")
        self.assertEqual(body["data"]["status"], "PRESENT")
        self.assertEqual(body["data"]["check_in_method"], "MANUAL")
        self.assertEqual(body["data"]["registration_reference"], self.registration.reference)
        self.assertEqual(body["data"]["event_id"], str(self.event.id))

    # --- Données manquantes ou mauvaises ------------------------------
    def test_missing_registration_id_returns_400(self):
        response = self.post_check_in(self.organizer)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("registration_id", response.json()["errors"])

    def test_invalid_uuid_returns_400(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(CHECK_IN_URL, {"registration_id": "abc"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_registration_returns_404(self):
        response = self.post_check_in(self.organizer, uuid.uuid4())
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_event_id_sent_by_frontend_is_ignored(self):
        """Un event_id ajouté par le frontend n'a aucun effet : l'événement vient de l'inscription."""
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(
            CHECK_IN_URL,
            {"registration_id": str(self.registration.id), "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["event_id"], str(self.event.id))

    # --- Authentification et autorisation ----------------------------
    def test_anonymous_returns_401(self):
        response = self.post_check_in(None, self.registration.id)
        self.assertEqual(response.status_code, 401)

    def test_participant_returns_403(self):
        response = self.post_check_in(self.participant, self.registration.id)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_other_organizer_returns_403(self):
        response = self.post_check_in(self.other_organizer, self.registration.id)
        self.assertEqual(response.status_code, 403)

    def test_admin_returns_201(self):
        response = self.post_check_in(self.admin, self.registration.id)
        self.assertEqual(response.status_code, 201)

    # --- Règle métier --------------------------------------------------
    def test_double_check_in_returns_409(self):
        self.post_check_in(self.organizer, self.registration.id)
        response = self.post_check_in(self.organizer, self.registration.id)
        self.assertEqual(response.status_code, 409)
        self.assertIn("déjà enregistré comme présent", response.json()["message"])
        self.assertEqual(Attendance.objects.count(), 1)


@FAST_HASHER
class MarkAbsentApiTests(AttendanceTestDataMixin, APITestCase):

    def test_mark_absent_returns_200(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(
            MARK_ABSENT_URL, {"registration_id": str(self.registration.id)}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ABSENT")
        self.assertIsNone(response.json()["data"]["checked_in_at"])

    def test_participant_cannot_mark_absent(self):
        self.client.force_authenticate(user=self.participant)
        response = self.client.post(
            MARK_ABSENT_URL, {"registration_id": str(self.registration.id)}, format="json",
        )
        self.assertEqual(response.status_code, 403)


@FAST_HASHER
class ReadAttendanceApiTests(AttendanceTestDataMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.other_participant = self.make_user("koffi@test.com")
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(
            CHECK_IN_URL, {"registration_id": str(self.registration.id)}, format="json",
        )
        self.attendance_id = response.json()["data"]["id"]
        self.client.force_authenticate(user=None)

    # --- /api/attendance/me/ -------------------------------------------
    def test_me_lists_own_attendance_paginated(self):
        self.client.force_authenticate(user=self.participant)
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["event_title"], self.event.title)
        # Information interne non exposée au participant
        self.assertNotIn("recorded_by_name", data["results"][0])

    def test_me_does_not_show_other_people_attendance(self):
        self.client.force_authenticate(user=self.other_participant)
        response = self.client.get(ME_URL)
        self.assertEqual(response.json()["data"]["count"], 0)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(ME_URL).status_code, 401)

    # --- /api/attendance/{id}/ -----------------------------------------
    def test_detail_for_organizer(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.get(detail_url(self.attendance_id))
        self.assertEqual(response.status_code, 200)
        self.assertIn("participant_email", response.json()["data"])

    def test_detail_for_participant_owner(self):
        self.client.force_authenticate(user=self.participant)
        response = self.client.get(detail_url(self.attendance_id))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("participant_email", response.json()["data"])

    def test_detail_forbidden_for_other_participant(self):
        """Protection IDOR : connaître l'UUID ne suffit pas."""
        self.client.force_authenticate(user=self.other_participant)
        response = self.client.get(detail_url(self.attendance_id))
        self.assertEqual(response.status_code, 403)

    def test_detail_unknown_returns_404(self):
        self.client.force_authenticate(user=self.organizer)
        self.assertEqual(self.client.get(detail_url(uuid.uuid4())).status_code, 404)

    # --- /api/registrations/{id}/attendance/ ---------------------------
    def test_registration_attendance_after_check_in(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.get(registration_attendance_url(self.registration.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["checked_in"])

    def test_registration_attendance_before_check_in(self):
        registration = self.make_registration(self.other_participant, self.event)
        self.client.force_authenticate(user=self.organizer)
        response = self.client.get(registration_attendance_url(registration.id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["checked_in"])
        self.assertIsNone(response.json()["data"]["attendance"])

    def test_registration_attendance_forbidden_for_other_participant(self):
        self.client.force_authenticate(user=self.other_participant)
        response = self.client.get(registration_attendance_url(self.registration.id))
        self.assertEqual(response.status_code, 403)
