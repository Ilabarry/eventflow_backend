"""
Tests du module Notifications d'EVENTFLOW.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .constants import NotificationType
from .models import Notification

User = get_user_model()


class NotificationAPITests(TestCase):
    """Tests des endpoints de notifications."""

    def setUp(self):
        """Crée deux utilisateurs et des notifications pour Alice."""
        self.alice = User.objects.create_user(
            email="alice@example.test",
            password="TestPass123!",
            first_name="Alice",
            last_name="Test",
            phone="+221770000001",
        )
        self.bob = User.objects.create_user(
            email="bob@example.test",
            password="TestPass123!",
            first_name="Bob",
            last_name="Test",
            phone="+221770000002",
        )

        # Notifications pour Alice
        self.alice_notif_read = Notification.objects.create(
            user=self.alice,
            title="Inscription confirmée",
            message="Votre inscription est confirmée.",
            type=NotificationType.EVENT_PUBLICATION,
            is_read=True,
        )
        self.alice_notif_unread = Notification.objects.create(
            user=self.alice,
            title="Nouvel événement",
            message="Un nouvel événement est disponible.",
            type=NotificationType.EVENT_PUBLICATION,
            is_read=False,
        )

        # Notification pour Bob
        self.bob_notif = Notification.objects.create(
            user=self.bob,
            title="Notification de Bob",
            message="Message pour Bob.",
            type=NotificationType.EVENT_PUBLICATION,
            is_read=False,
        )

        self.client = APIClient()

    # ------------------------------------------------------------------
    # TESTS DE SÉCURITÉ
    # ------------------------------------------------------------------
    def test_anonymous_user_cannot_list_notifications(self):
        """Un utilisateur non authentifié ne peut pas consulter l'API."""
        response = self.client.get(reverse("notifications:list"))
        self.assertEqual(response.status_code, 401)

    def test_list_contains_only_current_users_notifications(self):
        """Alice ne reçoit que ses propres notifications."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("notifications:list"))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        results = data["results"] if "results" in data else data
        self.assertEqual(len(results), 2)
        ids = {item["id"] for item in results}
        self.assertIn(str(self.alice_notif_read.id), ids)
        self.assertIn(str(self.alice_notif_unread.id), ids)
        self.assertNotIn(str(self.bob_notif.id), ids)

    def test_user_cannot_view_another_users_notification(self):
        """La consultation d'une notification étrangère renvoie 404."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(
            reverse("notifications:detail", args=[self.bob_notif.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_another_users_notification(self):
        """Alice ne peut pas supprimer la notification de Bob."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.delete(
            reverse("notifications:detail", args=[self.bob_notif.id])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=self.bob_notif.pk).exists())

    # ------------------------------------------------------------------
    # TESTS DE LECTURE
    # ------------------------------------------------------------------
    def test_unread_count_is_user_specific(self):
        """Le compteur ne compte que les notifications d'Alice."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("notifications:unread-count"))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["unread_count"], 1)

    def test_user_can_mark_notification_as_read(self):
        """Alice peut marquer sa notification comme lue."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.patch(
            reverse("notifications:mark-read", args=[self.alice_notif_unread.id])
        )
        self.assertEqual(response.status_code, 200)
        self.alice_notif_unread.refresh_from_db()
        self.assertTrue(self.alice_notif_unread.is_read)
        self.assertIsNotNone(self.alice_notif_unread.read_at)

    def test_mark_all_read_only_updates_current_user(self):
        """Le marquage global ne modifie pas les notifications de Bob."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.patch(reverse("notifications:read-all"))
        self.assertEqual(response.status_code, 200)
        self.alice_notif_unread.refresh_from_db()
        self.assertTrue(self.alice_notif_unread.is_read)
        # Bob non affecté
        self.bob_notif.refresh_from_db()
        self.assertFalse(self.bob_notif.is_read)

    # ------------------------------------------------------------------
    # TESTS DE SUPPRESSION
    # ------------------------------------------------------------------
    def test_user_can_delete_own_notification(self):
        """Alice peut supprimer sa propre notification."""
        self.client.force_authenticate(user=self.alice)
        response = self.client.delete(
            reverse("notifications:detail", args=[self.alice_notif_read.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Notification.objects.filter(pk=self.alice_notif_read.pk).exists()
        )