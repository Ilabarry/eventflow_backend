"""
Tests de la phase S3 : événements (consultation, annulation) et catégories.

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
from apps.events.constants import EventStatus
from apps.events.models import Category
from apps.registrations.constants import RegistrationStatus
from apps.supervision.constants import AuditAction, AuditResult
from apps.supervision.models import AuditLog
from apps.supervision.test_security import FAST_HASHER, SupervisionUsersMixin

EVENTS_URL = "/api/supervision/events/"
CATEGORIES_URL = "/api/supervision/categories/"
REASON = {"reason": "Contenu contraire aux règles de la plateforme"}

make_event = AttendanceTestDataMixin.make_event
make_registration = AttendanceTestDataMixin.make_registration


# ==================================================================
# ÉVÉNEMENTS
# ==================================================================
@FAST_HASHER
class SupervisionEventApiTests(SupervisionUsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Tech")
        self.event = make_event(self.organizer, self.category, starts_in=timedelta(days=3))
        self.draft = make_event(
            self.organizer, self.category, status=EventStatus.DRAFT, starts_in=timedelta(days=10),
        )
        self.completed = make_event(self.organizer, self.category, status=EventStatus.COMPLETED,
                                    starts_in=timedelta(days=-10))
        registration = make_registration(self.participant, self.event)
        make_registration(self.role_admin, self.event, status=RegistrationStatus.PENDING)
        Attendance.objects.create(
            registration=registration, status=AttendanceStatus.PRESENT,
            checked_in_at=self.event.start_at, check_in_method=CheckInMethod.MANUAL,
        )
        self.client.force_authenticate(user=self.role_admin)

    def cancel(self, event, data=None, user=None):
        if user:
            self.client.force_authenticate(user=user)
        return self.client.post(f"{EVENTS_URL}{event.id}/cancel/",
                                REASON if data is None else data, format="json")

    # --- consultation -------------------------------------------------------
    def test_admin_sees_all_statuses_including_drafts(self):
        data = self.client.get(EVENTS_URL).json()["data"]
        self.assertEqual(data["count"], 3)

    def test_list_counters(self):
        rows = {r["id"]: r for r in self.client.get(EVENTS_URL).json()["data"]["results"]}
        row = rows[str(self.event.id)]
        self.assertEqual(row["registrations_confirmed"], 1)  # PENDING non compté
        self.assertEqual(row["attendances_present"], 1)
        self.assertEqual(row["organizer_email"], "orga@test.com")

    def test_access_url_is_never_exposed(self):
        row = self.client.get(EVENTS_URL).json()["data"]["results"][0]
        self.assertNotIn("access_url", row)

    def test_filter_by_status(self):
        results = self.client.get(EVENTS_URL, {"status": "DRAFT"}).json()["data"]["results"]
        self.assertEqual([r["id"] for r in results], [str(self.draft.id)])

    def test_filter_by_organizer(self):
        self.assertEqual(
            self.client.get(EVENTS_URL, {"organizer": str(self.organizer.id)}).json()["data"]["count"], 3,
        )
        self.assertEqual(
            self.client.get(EVENTS_URL, {"organizer": str(self.participant.id)}).json()["data"]["count"], 0,
        )

    def test_invalid_status_filter_returns_400(self):
        self.assertEqual(self.client.get(EVENTS_URL, {"status": "HACK"}).status_code, 400)

    def test_detail_counters(self):
        data = self.client.get(f"{EVENTS_URL}{self.event.id}/").json()["data"]
        self.assertEqual(data["registrations_confirmed"], 1)
        self.assertEqual(data["registrations_pending"], 1)
        self.assertEqual(data["registrations_cancelled"], 0)

    def test_detail_unknown_returns_404(self):
        self.assertEqual(self.client.get(f"{EVENTS_URL}{uuid.uuid4()}/").status_code, 404)

    def test_no_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as small:
            self.client.get(EVENTS_URL)
        for _ in range(4):
            make_event(self.organizer, self.category, starts_in=timedelta(days=5))
        with CaptureQueriesContext(connection) as large:
            self.client.get(EVENTS_URL)
        self.assertEqual(len(small), len(large))

    # --- annulation ---------------------------------------------------------
    def test_cancel_published_event(self):
        response = self.cancel(self.event)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], EventStatus.CANCELLED)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.CANCELLED)

    def test_cancellation_is_audited(self):
        self.cancel(self.event)
        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, AuditAction.EVENT_CANCELLED)
        self.assertEqual(entry.reason, REASON["reason"])
        self.assertEqual(entry.metadata["previous_status"], EventStatus.PUBLISHED)
        self.assertEqual(entry.metadata["confirmed_registrations"], 1)

    def test_cancel_draft(self):
        self.assertEqual(self.cancel(self.draft).status_code, 200)

    def test_cancel_without_reason_returns_400(self):
        self.assertEqual(self.cancel(self.event, data={}).status_code, 400)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.PUBLISHED)

    def test_cancel_twice_returns_409(self):
        self.cancel(self.event)
        self.assertEqual(self.cancel(self.event).status_code, 409)
        self.assertEqual(AuditLog.objects.count(), 1)  # l'échec ne crée pas de ligne

    def test_cancel_completed_event_returns_400(self):
        self.assertEqual(self.cancel(self.completed).status_code, 400)
        self.assertFalse(AuditLog.objects.exists())

    def test_cancel_unknown_returns_404(self):
        response = self.client.post(f"{EVENTS_URL}{uuid.uuid4()}/cancel/", REASON, format="json")
        self.assertEqual(response.status_code, 404)

    def test_no_publish_route_for_admin(self):
        """Décision B : l'administrateur ne publie pas les événements."""
        response = self.client.post(f"{EVENTS_URL}{self.draft.id}/publish/", REASON, format="json")
        self.assertEqual(response.status_code, 404)

    def test_organizer_cannot_use_supervision_cancel(self):
        self.assertEqual(self.cancel(self.event, user=self.organizer).status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.PUBLISHED)

    def test_anonymous_returns_401(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(EVENTS_URL).status_code, 401)


# ==================================================================
# CATÉGORIES
# ==================================================================
@FAST_HASHER
class SupervisionCategoryApiTests(SupervisionUsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.used = Category.objects.create(name="Tech")
        self.unused = Category.objects.create(name="Musique")
        make_event(self.organizer, self.used, starts_in=timedelta(days=3))
        self.client.force_authenticate(user=self.role_admin)

    def url(self, category, suffix=""):
        return f"{CATEGORIES_URL}{category.id}/{suffix}"

    # --- consultation -------------------------------------------------------
    def test_list_with_counters(self):
        rows = {r["name"]: r for r in self.client.get(CATEGORIES_URL).json()["data"]["results"]}
        self.assertEqual(rows["Tech"]["events_total"], 1)
        self.assertEqual(rows["Musique"]["events_total"], 0)

    def test_list_includes_inactive_categories(self):
        self.unused.is_active = False
        self.unused.save()
        self.assertEqual(self.client.get(CATEGORIES_URL).json()["data"]["count"], 2)
        self.assertEqual(self.client.get(CATEGORIES_URL, {"is_active": "false"}).json()["data"]["count"], 1)

    def test_detail_unknown_returns_404(self):
        self.assertEqual(self.client.get(f"{CATEGORIES_URL}{uuid.uuid4()}/").status_code, 404)

    # --- création -----------------------------------------------------------
    def test_create(self):
        response = self.client.post(CATEGORIES_URL, {"name": "Sport", "icon": "ball"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["slug"], "sport")
        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, AuditAction.CATEGORY_CREATED)

    def test_create_missing_name_returns_400(self):
        self.assertEqual(self.client.post(CATEGORIES_URL, {}, format="json").status_code, 400)

    def test_create_duplicate_name_case_insensitive_returns_400(self):
        self.assertEqual(self.client.post(CATEGORIES_URL, {"name": "tech"}, format="json").status_code, 400)

    def test_create_same_slug_returns_409_not_500(self):
        """« Tech ! » donne le même slug que « Tech » : erreur propre, pas de 500."""
        response = self.client.post(CATEGORIES_URL, {"name": "Tech !"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(AuditLog.objects.exists())

    def test_cannot_set_is_active_on_create(self):
        response = self.client.post(CATEGORIES_URL, {"name": "Danse", "is_active": False}, format="json")
        self.assertTrue(response.json()["data"]["is_active"])  # champ ignoré

    # --- modification -------------------------------------------------------
    def test_update_records_before_after(self):
        response = self.client.patch(self.url(self.unused), {"description": "Concerts"}, format="json")
        self.assertEqual(response.status_code, 200)
        changes = AuditLog.objects.get().metadata["changes"]
        self.assertEqual(changes, {"description": {"before": "", "after": "Concerts"}})

    def test_update_without_change_writes_no_audit(self):
        self.client.patch(self.url(self.unused), {"name": "Musique"}, format="json")
        self.assertFalse(AuditLog.objects.exists())

    def test_update_to_existing_name_returns_400(self):
        self.assertEqual(self.client.patch(self.url(self.unused), {"name": "TECH"}, format="json").status_code, 400)

    # --- désactivation / réactivation -------------------------------------
    def test_deactivate_used_category_keeps_events(self):
        response = self.client.post(self.url(self.used, "deactivate/"), REASON, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["is_active"])
        self.assertEqual(response.json()["data"]["events_total"], 1)
        self.assertEqual(AuditLog.objects.get().action, AuditAction.CATEGORY_DEACTIVATED)

    def test_deactivate_without_reason_returns_400(self):
        self.assertEqual(self.client.post(self.url(self.used, "deactivate/"), {}, format="json").status_code, 400)

    def test_deactivate_twice_returns_409(self):
        self.client.post(self.url(self.used, "deactivate/"), REASON, format="json")
        self.assertEqual(self.client.post(self.url(self.used, "deactivate/"), REASON, format="json").status_code, 409)

    def test_activate(self):
        self.client.post(self.url(self.used, "deactivate/"), REASON, format="json")
        response = self.client.post(self.url(self.used, "activate/"), REASON, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["is_active"])

    # --- suppression --------------------------------------------------------
    def test_delete_unused_category(self):
        self.assertEqual(self.client.delete(self.url(self.unused)).status_code, 200)
        self.assertFalse(Category.objects.filter(pk=self.unused.pk).exists())
        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, AuditAction.CATEGORY_DELETED)
        self.assertEqual(entry.metadata["name"], "Musique")

    def test_delete_used_category_returns_409(self):
        self.assertEqual(self.client.delete(self.url(self.used)).status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.used.pk).exists())
        self.assertFalse(AuditLog.objects.exists())

    def test_delete_unknown_returns_404(self):
        self.assertEqual(self.client.delete(f"{CATEGORIES_URL}{uuid.uuid4()}/").status_code, 404)

    # --- sécurité -------------------------------------------------------------
    def test_organizer_cannot_create(self):
        self.client.force_authenticate(user=self.organizer)
        self.assertEqual(self.client.post(CATEGORIES_URL, {"name": "Pirate"}, format="json").status_code, 403)
        self.assertFalse(Category.objects.filter(name="Pirate").exists())

    def test_participant_cannot_delete(self):
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.delete(self.url(self.unused)).status_code, 403)
        self.assertTrue(Category.objects.filter(pk=self.unused.pk).exists())

    def test_audit_results_are_success(self):
        self.client.post(CATEGORIES_URL, {"name": "Sport"}, format="json")
        self.assertEqual(AuditLog.objects.get().result, AuditResult.SUCCESS)
