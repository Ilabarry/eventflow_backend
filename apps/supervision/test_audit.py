"""
Tests du journal d'audit (phase S1) : écriture, nettoyage, immutabilité, API.
"""

import uuid

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from rest_framework.test import APITestCase

from apps.supervision.constants import FILTERED_VALUE, AuditAction, AuditEntity, AuditResult
from apps.supervision.models import AuditLog
from apps.supervision.services import AuditService, sanitize_metadata
from apps.supervision.test_security import AUDIT_URL, FAST_HASHER, SupervisionUsersMixin


def log_example(actor, **extra):
    data = dict(
        actor=actor,
        action=AuditAction.USER_SUSPENDED,
        entity_type=AuditEntity.USER,
        entity_id=uuid.uuid4(),
        description="Suspension de test",
        reason="Comportement abusif",
    )
    data.update(extra)
    return AuditService.log(**data)


# ==================================================================
# Nettoyage des métadonnées
# ==================================================================
class SanitizeMetadataTests(TestCase):

    def test_sensitive_keys_are_filtered_at_any_depth(self):
        cleaned = sanitize_metadata({
            "email": "awa@test.com",
            "password": "secret123",
            "nested": {"refresh": "eyJ...", "access_token": "eyJ...", "city": "Cotonou"},
            "items": [{"card_number": "4111111111111111"}],
        })
        self.assertEqual(cleaned["email"], "awa@test.com")
        self.assertEqual(cleaned["password"], FILTERED_VALUE)
        self.assertEqual(cleaned["nested"]["refresh"], FILTERED_VALUE)
        self.assertEqual(cleaned["nested"]["access_token"], FILTERED_VALUE)
        self.assertEqual(cleaned["nested"]["city"], "Cotonou")
        self.assertEqual(cleaned["items"][0]["card_number"], FILTERED_VALUE)

    def test_short_exact_keys_do_not_overmatch(self):
        """« pin » est masqué, mais pas « shipping » qui le contient."""
        cleaned = sanitize_metadata({"pin": "1234", "shipping": "standard"})
        self.assertEqual(cleaned["pin"], FILTERED_VALUE)
        self.assertEqual(cleaned["shipping"], "standard")


# ==================================================================
# Écriture et immutabilité
# ==================================================================
@FAST_HASHER
class AuditServiceTests(SupervisionUsersMixin, TestCase):

    def test_log_records_who_what_where(self):
        request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.7", HTTP_USER_AGENT="Firefox/140")
        entry = log_example(self.role_admin, request=request, metadata={"password": "x", "old_status": "active"})
        self.assertEqual(entry.actor, self.role_admin)
        self.assertEqual(entry.actor_email, "admin.role@test.com")
        self.assertEqual(entry.ip_address, "10.0.0.7")
        self.assertEqual(entry.user_agent, "Firefox/140")
        self.assertEqual(entry.result, AuditResult.SUCCESS)
        self.assertEqual(entry.metadata, {"password": FILTERED_VALUE, "old_status": "active"})

    def test_x_forwarded_for_is_not_trusted(self):
        request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.7", HTTP_X_FORWARDED_FOR="1.2.3.4")
        self.assertEqual(log_example(self.role_admin, request=request).ip_address, "10.0.0.7")

    def test_long_user_agent_is_truncated(self):
        request = RequestFactory().get("/", HTTP_USER_AGENT="A" * 1000)
        self.assertEqual(len(log_example(self.role_admin, request=request).user_agent), 255)

    def test_entry_cannot_be_modified(self):
        entry = log_example(self.role_admin)
        entry.description = "falsifié"
        with self.assertRaises(PermissionDenied):
            entry.save()

    def test_entry_cannot_be_deleted(self):
        entry = log_example(self.role_admin)
        with self.assertRaises(PermissionDenied):
            entry.delete()

    def test_bulk_update_and_delete_are_blocked(self):
        log_example(self.role_admin)
        with self.assertRaises(PermissionDenied):
            AuditLog.objects.all().update(description="falsifié")
        with self.assertRaises(PermissionDenied):
            AuditLog.objects.all().delete()
        self.assertEqual(AuditLog.objects.get().description, "Suspension de test")

    def test_actor_identity_kept_if_account_disappears(self):
        entry = log_example(self.role_admin)
        self.assertEqual(entry.actor_email, "admin.role@test.com")


# ==================================================================
# API de consultation
# ==================================================================
@FAST_HASHER
class AuditLogApiTests(SupervisionUsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.target_id = uuid.uuid4()
        self.entry = log_example(self.role_admin, entity_id=self.target_id)
        log_example(self.super_admin, action=AuditAction.EVENT_CANCELLED, entity_type=AuditEntity.EVENT)
        log_example(self.role_admin, result=AuditResult.DENIED, description="Tentative refusée")
        self.client.force_authenticate(user=self.staff_admin)

    def test_list_is_paginated_newest_first(self):
        data = self.client.get(AUDIT_URL).json()["data"]
        self.assertEqual(data["count"], 3)
        self.assertEqual(data["results"][0]["description"], "Tentative refusée")

    def test_filter_by_action(self):
        data = self.client.get(AUDIT_URL, {"action": "EVENT_CANCELLED"}).json()["data"]
        self.assertEqual(data["count"], 1)

    def test_filter_by_entity(self):
        data = self.client.get(AUDIT_URL, {"entity_type": "USER", "entity_id": str(self.target_id)}).json()["data"]
        self.assertEqual(data["count"], 1)

    def test_filter_by_actor(self):
        data = self.client.get(AUDIT_URL, {"actor": str(self.super_admin.id)}).json()["data"]
        self.assertEqual(data["count"], 1)

    def test_filter_by_result(self):
        self.assertEqual(self.client.get(AUDIT_URL, {"result": "DENIED"}).json()["data"]["count"], 1)

    def test_search(self):
        self.assertEqual(self.client.get(AUDIT_URL, {"search": "super@"}).json()["data"]["count"], 1)

    def test_invalid_filter_returns_400(self):
        self.assertEqual(self.client.get(AUDIT_URL, {"action": "HACK"}).status_code, 400)

    def test_invalid_ordering_returns_400(self):
        self.assertEqual(self.client.get(AUDIT_URL, {"ordering": "metadata"}).status_code, 400)

    def test_page_size_is_capped_at_50(self):
        data = self.client.get(AUDIT_URL, {"page_size": 100000}).json()["data"]
        self.assertEqual(data["page_size"], 50)

    def test_detail(self):
        response = self.client.get(f"{AUDIT_URL}{self.entry.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["reason"], "Comportement abusif")

    def test_detail_unknown_returns_404(self):
        self.assertEqual(self.client.get(f"{AUDIT_URL}{uuid.uuid4()}/").status_code, 404)

    def test_api_is_strictly_read_only(self):
        """Aucune méthode d'écriture n'existe : 405 Method Not Allowed."""
        detail = f"{AUDIT_URL}{self.entry.id}/"
        self.assertEqual(self.client.post(AUDIT_URL, {}, format="json").status_code, 405)
        self.assertEqual(self.client.put(detail, {}, format="json").status_code, 405)
        self.assertEqual(self.client.patch(detail, {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.assertEqual(AuditLog.objects.count(), 3)

    def test_participant_cannot_read_audit(self):
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.get(AUDIT_URL).status_code, 403)
