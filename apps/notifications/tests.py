
"""
Tests du module Notifications d'EVENTFLOW.

Vérifie les accès API, l'isolation entre utilisateurs,
la lecture et la suppression des notifications.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Notification


User = get_user_model()


class NotificationAPITests(APITestCase):
    """Teste les endpoints du module Notifications."""

    def setUp(self):
        # Création de deux utilisateurs indépendants.
        self.user = User.objects.create_user(
            email="alice@example.com",
            password="TestPassword123!",
            first_name="Alice",
            last_name="Test",
            phone="+221770000001",
        )

        self.other_user = User.objects.create_user(
            email="bob@example.com",
            password="TestPassword123!",
            first_name="Bob",
            last_name="Test",
            phone="+221770000002",
        )

        # Une notification non lue pour Alice.
        self.unread_notification = Notification.objects.create(
            user=self.user,
            title="Nouvel événement",
            message="Un événement vient d'être publié.",
            type=Notification.Type.EVENT_PUBLICATION,
        )

        # Une notification déjà lue pour Alice.
        self.read_notification = Notification.objects.create(
            user=self.user,
            title="Inscription confirmée",
            message="Votre inscription est confirmée.",
            type=Notification.Type.REGISTRATION,
            is_read=True,
            read_at=timezone.now(),
        )

        # Une notification appartenant à Bob.
        self.other_notification = Notification.objects.create(
            user=self.other_user,
            title="Message privé",
            message="Cette notification appartient à Bob.",
            type=Notification.Type.SYSTEM,
        )

        # Alice est l'utilisateur connecté pour les tests.
        self.client.force_authenticate(user=self.user)

    def test_list_contains_only_current_users_notifications(self):
        """Alice ne reçoit que ses propres notifications."""

        response = self.client.get(
            "/api/notifications/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["data"]["results"]
        returned_ids = {item["id"] for item in results}

        self.assertEqual(len(results), 2)
        self.assertIn(str(self.unread_notification.id), returned_ids)
        self.assertIn(str(self.read_notification.id), returned_ids)
        self.assertNotIn(str(self.other_notification.id), returned_ids)

    def test_unread_count_is_user_specific(self):
        """Le compteur ne compte que les notifications d'Alice."""

        response = self.client.get(
            "/api/notifications/unread-count/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["unread_count"], 1)

    def test_user_can_mark_notification_as_read(self):
        """Alice peut marquer sa notification comme lue."""

        response = self.client.patch(
            f"/api/notifications/{self.unread_notification.id}/read/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.unread_notification.refresh_from_db()

        self.assertTrue(self.unread_notification.is_read)
        self.assertIsNotNone(self.unread_notification.read_at)

    def test_mark_all_read_only_updates_current_user(self):
        """Le marquage global ne modifie pas les notifications de Bob."""

        response = self.client.patch(
            "/api/notifications/read-all/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["updated_count"], 1)

        self.unread_notification.refresh_from_db()
        self.other_notification.refresh_from_db()

        self.assertTrue(self.unread_notification.is_read)
        self.assertFalse(self.other_notification.is_read)

    def test_user_cannot_view_another_users_notification(self):
        """La consultation d'une notification étrangère renvoie 404."""

        response = self.client.get(
            f"/api/notifications/{self.other_notification.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_delete_another_users_notification(self):
        """Alice ne peut pas supprimer la notification de Bob."""

        response = self.client.delete(
            f"/api/notifications/{self.other_notification.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Notification.objects.filter(
                pk=self.other_notification.id
            ).exists()
        )

    def test_user_can_delete_own_notification(self):
        """Alice peut supprimer sa propre notification."""

        response = self.client.delete(
            f"/api/notifications/{self.unread_notification.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            Notification.objects.filter(
                pk=self.unread_notification.id
            ).exists()
        )

    def test_anonymous_user_cannot_list_notifications(self):
        """Un utilisateur non authentifié ne peut pas consulter l'API."""

        self.client.force_authenticate(user=None)

        response = self.client.get(
            "/api/notifications/"
        )

        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])
