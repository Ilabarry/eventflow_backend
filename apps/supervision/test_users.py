"""
Tests de la phase S2 : utilisateurs, organisateurs, suspension / réactivation.

Lancer :
    python manage.py test apps.supervision
"""

import uuid
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.constants import ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.attendance.tests import AttendanceTestDataMixin
from apps.events.constants import EventStatus
from apps.events.models import Category
from apps.registrations.constants import RegistrationStatus
from apps.supervision.constants import AuditAction, AuditResult
from apps.supervision.exceptions import ActorNoLongerAdmin, LastActiveAdmin
from apps.supervision.models import AuditLog
from apps.supervision.services import UserSupervisionService
from apps.supervision.test_security import FAST_HASHER, SupervisionUsersMixin
from apps.supervision.validators import ensure_not_last_active_admin

USERS_URL = "/api/supervision/users/"
ORGANIZERS_URL = "/api/supervision/organizers/"
REASON = {"reason": "Événements frauduleux signalés"}

make_event = AttendanceTestDataMixin.make_event
make_registration = AttendanceTestDataMixin.make_registration


def user_url(user_id, suffix=""):
    return f"{USERS_URL}{user_id}/{suffix}"


# ==================================================================
# LISTE ET FICHE DES UTILISATEURS
# ==================================================================
@FAST_HASHER
class UserListApiTests(SupervisionUsersMixin, APITestCase):

    def get_list(self, user=None, **params):
        self.client.force_authenticate(user=user or self.role_admin)
        return self.client.get(USERS_URL, params)

    def test_admin_sees_all_users(self):
        response = self.get_list()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["count"], 5)

    def test_no_password_in_payload(self):
        row = self.get_list().json()["data"]["results"][0]
        self.assertNotIn("password", row)
        self.assertIn("roles", row)

    def test_filter_by_role(self):
        results = self.get_list(role=ROLE_ORGANIZER).json()["data"]["results"]
        self.assertEqual([r["email"] for r in results], ["orga@test.com"])

    def test_filter_suspended_accounts(self):
        self.participant.is_active = False
        self.participant.save()
        results = self.get_list(is_active="false").json()["data"]["results"]
        self.assertEqual([r["email"] for r in results], ["participant@test.com"])

    def test_search(self):
        self.assertEqual(self.get_list(search="orga@").json()["data"]["count"], 1)

    def test_is_admin_flag(self):
        results = {r["email"]: r["is_admin"] for r in self.get_list().json()["data"]["results"]}
        self.assertTrue(results["admin.role@test.com"])
        self.assertTrue(results["admin.staff@test.com"])
        self.assertFalse(results["participant@test.com"])

    def test_invalid_role_returns_400(self):
        self.assertEqual(self.get_list(role="dieu").status_code, 400)

    def test_invalid_ordering_returns_400(self):
        self.assertEqual(self.get_list(ordering="password").status_code, 400)

    def test_participant_is_forbidden(self):
        self.assertEqual(self.get_list(user=self.participant).status_code, 403)

    def test_anonymous_returns_401(self):
        self.assertEqual(self.client.get(USERS_URL).status_code, 401)

    def test_no_n_plus_one_queries(self):
        self.client.force_authenticate(user=self.role_admin)
        with CaptureQueriesContext(connection) as small:
            self.client.get(USERS_URL)
        for i in range(5):
            self.make_user(f"extra{i}@test.com", ROLE_PARTICIPANT)
        with CaptureQueriesContext(connection) as large:
            self.client.get(USERS_URL)
        self.assertEqual(len(small), len(large))


@FAST_HASHER
class UserDetailAndActivityTests(SupervisionUsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        category = Category.objects.create(name="Tech")
        self.event = make_event(self.organizer, category)
        make_event(self.organizer, category, status=EventStatus.DRAFT, starts_in=timedelta(days=3))
        self.registration = make_registration(self.participant, self.event)
        Attendance.objects.create(
            registration=self.registration,
            status=AttendanceStatus.PRESENT,
            checked_in_at=self.event.start_at,
            check_in_method=CheckInMethod.MANUAL,
        )
        self.client.force_authenticate(user=self.role_admin)

    def test_participant_detail_counts(self):
        data = self.client.get(user_url(self.participant.id)).json()["data"]
        self.assertEqual(data["active_registrations_count"], 1)
        self.assertEqual(data["attendances_present_count"], 1)
        self.assertEqual(data["organized_events_count"], 0)

    def test_organizer_detail_counts(self):
        data = self.client.get(user_url(self.organizer.id)).json()["data"]
        self.assertEqual(data["organized_events_count"], 2)

    def test_unknown_user_returns_404(self):
        self.assertEqual(self.client.get(user_url(uuid.uuid4())).status_code, 404)

    def test_activity(self):
        data = self.client.get(user_url(self.participant.id, "activity/")).json()["data"]
        self.assertEqual(data["registrations"]["total"], 1)
        self.assertEqual(data["registrations"]["recent"][0]["event_title"], "Conférence test")
        self.assertEqual(data["attendances"]["total"], 1)
        self.assertEqual(data["organized_events"]["total"], 0)

    def test_activity_unknown_user_returns_404(self):
        self.assertEqual(self.client.get(user_url(uuid.uuid4(), "activity/")).status_code, 404)


# ==================================================================
# SUSPENSION / RÉACTIVATION
# ==================================================================
@FAST_HASHER
class SuspendApiTests(SupervisionUsersMixin, APITestCase):

    def post(self, actor, target, action="suspend", data=None):
        self.client.force_authenticate(user=actor)
        return self.client.post(user_url(target.id, f"{action}/"), data if data is not None else REASON, format="json")

    # --- cas nominal -------------------------------------------------------
    def test_suspend_participant(self):
        response = self.post(self.role_admin, self.participant)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["is_active"])
        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_active)

    def test_suspension_is_audited(self):
        self.post(self.role_admin, self.participant)
        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, AuditAction.USER_SUSPENDED)
        self.assertEqual(entry.result, AuditResult.SUCCESS)
        self.assertEqual(entry.entity_id, str(self.participant.id))
        self.assertEqual(entry.reason, REASON["reason"])
        self.assertEqual(entry.actor, self.role_admin)

    def test_suspension_revokes_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.participant)
        self.post(self.role_admin, self.participant)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())
        self.client.force_authenticate(user=None)
        response = self.client.post("/api/auth/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_suspended_user_access_token_is_rejected(self):
        access = str(RefreshToken.for_user(self.participant).access_token)
        self.post(self.role_admin, self.participant)
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/users/me/").status_code, 401)

    def test_super_admin_can_suspend_an_admin(self):
        self.assertEqual(self.post(self.super_admin, self.role_admin).status_code, 200)

    # --- mauvaise donnée / donnée manquante --------------------------------
    def test_missing_reason_returns_400(self):
        response = self.post(self.role_admin, self.participant, data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.json()["errors"])
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_active)

    def test_too_short_reason_returns_400(self):
        self.assertEqual(self.post(self.role_admin, self.participant, data={"reason": "  ok "}).status_code, 400)

    def test_unknown_user_returns_404(self):
        self.client.force_authenticate(user=self.role_admin)
        response = self.client.post(user_url(uuid.uuid4(), "suspend/"), REASON, format="json")
        self.assertEqual(response.status_code, 404)

    def test_already_suspended_returns_409(self):
        self.post(self.role_admin, self.participant)
        self.assertEqual(self.post(self.role_admin, self.participant).status_code, 409)

    # --- garde-fous ---------------------------------------------------------
    def test_cannot_suspend_self_and_denial_is_audited(self):
        response = self.post(self.role_admin, self.role_admin)
        self.assertEqual(response.status_code, 403)
        self.role_admin.refresh_from_db()
        self.assertTrue(self.role_admin.is_active)
        # Le refus est conservé malgré l'erreur (écrit hors de la transaction annulée).
        entry = AuditLog.objects.get()
        self.assertEqual(entry.result, AuditResult.DENIED)
        self.assertEqual(entry.metadata["denial_code"], "cannot_change_own_status")

    def test_standard_admin_cannot_suspend_another_admin(self):
        response = self.post(self.role_admin, self.staff_admin)
        self.assertEqual(response.status_code, 403)
        self.staff_admin.refresh_from_db()
        self.assertTrue(self.staff_admin.is_active)
        self.assertEqual(AuditLog.objects.get().result, AuditResult.DENIED)

    def test_participant_cannot_suspend(self):
        self.assertEqual(self.post(self.participant, self.organizer).status_code, 403)
        self.organizer.refresh_from_db()
        self.assertTrue(self.organizer.is_active)
        self.assertFalse(AuditLog.objects.exists())

    def test_get_is_not_allowed_on_action(self):
        self.client.force_authenticate(user=self.role_admin)
        self.assertEqual(self.client.get(user_url(self.participant.id, "suspend/")).status_code, 405)

    # --- réactivation --------------------------------------------------------
    def test_activate_suspended_user(self):
        self.post(self.role_admin, self.participant)
        response = self.post(self.role_admin, self.participant, action="activate")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["is_active"])
        actions = list(AuditLog.objects.order_by("created_at").values_list("action", flat=True))
        self.assertEqual(actions, [AuditAction.USER_SUSPENDED, AuditAction.USER_ACTIVATED])

    def test_activate_active_user_returns_409(self):
        self.assertEqual(self.post(self.role_admin, self.participant, action="activate").status_code, 409)

    def test_standard_admin_cannot_reactivate_an_admin(self):
        self.staff_admin.is_active = False
        self.staff_admin.save()
        self.assertEqual(self.post(self.role_admin, self.staff_admin, action="activate").status_code, 403)

    def test_activate_missing_reason_returns_400(self):
        self.assertEqual(self.post(self.role_admin, self.participant, action="activate", data={}).status_code, 400)


@FAST_HASHER
class GuardServiceTests(SupervisionUsersMixin, TestCase):
    """Garde-fous testés directement sur le service et les validateurs."""

    def test_last_active_admin_cannot_be_suspended(self):
        # On ne garde qu'un seul administrateur actif.
        for admin in (self.staff_admin, self.super_admin):
            admin.is_active = False
            admin.save()
        with self.assertRaises(LastActiveAdmin):
            ensure_not_last_active_admin(self.role_admin)

    def test_actor_who_lost_admin_rights_is_refused(self):
        """Cas de concurrence : l'admin a été suspendu entre-temps."""
        self.role_admin.is_active = False
        self.role_admin.save()
        with self.assertRaises(ActorNoLongerAdmin):
            UserSupervisionService.suspend(
                actor=self.role_admin, user_id=self.participant.id, reason="Test de sécurité",
            )
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_active)
        self.assertEqual(AuditLog.objects.get().result, AuditResult.DENIED)


# ==================================================================
# ORGANISATEURS
# ==================================================================
@FAST_HASHER
class OrganizerApiTests(SupervisionUsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        category = Category.objects.create(name="Tech")
        upcoming = make_event(self.organizer, category, starts_in=timedelta(days=5))
        make_event(self.organizer, category)  # publié, déjà commencé
        make_event(self.organizer, category, status=EventStatus.CANCELLED, starts_in=timedelta(days=9))
        make_registration(self.participant, upcoming)
        make_registration(self.role_admin, upcoming, status=RegistrationStatus.CANCELLED)
        self.client.force_authenticate(user=self.role_admin)

    def test_list_contains_only_organizers_with_counts(self):
        results = self.client.get(ORGANIZERS_URL).json()["data"]["results"]
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["email"], "orga@test.com")
        self.assertEqual(row["events_total"], 3)
        self.assertEqual(row["events_published"], 2)
        self.assertEqual(row["events_upcoming"], 1)
        self.assertEqual(row["events_cancelled"], 1)
        self.assertEqual(row["registrations_confirmed"], 1)  # l'annulée n'est pas comptée

    def test_ordering_by_events_total(self):
        self.assertEqual(self.client.get(ORGANIZERS_URL, {"ordering": "-events_total"}).status_code, 200)

    def test_detail(self):
        response = self.client.get(f"{ORGANIZERS_URL}{self.organizer.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["events_total"], 3)

    def test_participant_is_not_an_organizer(self):
        self.assertEqual(self.client.get(f"{ORGANIZERS_URL}{self.participant.id}/").status_code, 404)

    def test_organizer_cannot_list_organizers(self):
        self.client.force_authenticate(user=self.organizer)
        self.assertEqual(self.client.get(ORGANIZERS_URL).status_code, 403)
