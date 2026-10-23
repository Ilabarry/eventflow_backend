"""
Tests de sécurité du socle Supervision (phase S1).

Règle testée : SEULS les administrateurs actifs accèdent à /api/supervision/,
quel que soit ce que le client envoie.

Lancer :
    python manage.py test apps.supervision
"""

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.constants import ROLE_ADMIN, ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.accounts.models import User

FAST_HASHER = override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
AUDIT_URL = "/api/supervision/audit-logs/"


class SupervisionUsersMixin:
    """Crée un utilisateur de chaque niveau d'accès."""

    _counter = 0

    @classmethod
    def make_user(cls, email, role=None, **extra):
        cls._counter += 1
        user = User.objects.create_user(
            email=email,
            password="TestPass2026",
            first_name="Test",
            last_name=email.split("@")[0],
            phone=f"+2299100{cls._counter:04d}",
            **extra,
        )
        if role:
            user.add_role(role)
        return user

    def setUp(self):
        cache.clear()  # remet à zéro les compteurs de limitation du débit
        self.participant = self.make_user("participant@test.com", ROLE_PARTICIPANT)
        self.organizer = self.make_user("orga@test.com", ROLE_ORGANIZER)
        self.role_admin = self.make_user("admin.role@test.com", ROLE_ADMIN)
        self.staff_admin = self.make_user("admin.staff@test.com", is_staff=True)
        self.super_admin = self.make_user("super@test.com", is_staff=True, is_superuser=True)


@FAST_HASHER
class SupervisionAccessTests(SupervisionUsersMixin, APITestCase):

    def get_as(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get(AUDIT_URL)

    def test_anonymous_returns_401(self):
        self.assertEqual(self.client.get(AUDIT_URL).status_code, 401)

    def test_participant_returns_403(self):
        response = self.get_as(self.participant)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])

    def test_organizer_returns_403(self):
        self.assertEqual(self.get_as(self.organizer).status_code, 403)

    def test_admin_by_role_has_access(self):
        self.assertEqual(self.get_as(self.role_admin).status_code, 200)

    def test_staff_admin_has_access(self):
        self.assertEqual(self.get_as(self.staff_admin).status_code, 200)

    def test_super_admin_has_access(self):
        self.assertEqual(self.get_as(self.super_admin).status_code, 200)

    def test_suspended_admin_loses_access(self):
        """Un admin suspendu (is_active=False) n'a plus aucun accès."""
        self.role_admin.is_active = False
        self.role_admin.save()
        self.assertIn(self.get_as(self.role_admin).status_code, (401, 403))


@FAST_HASHER
class SupervisionThrottleTests(SupervisionUsersMixin, APITestCase):

    def test_read_rate_limit_returns_429(self):
        rates = {"supervision_read": "3/min", "supervision_action": "3/min"}
        with self.settings(REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": rates,
        }):
            self.client.force_authenticate(user=self.role_admin)
            codes = [self.client.get(AUDIT_URL).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])
