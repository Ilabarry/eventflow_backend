from django.test import TestCase

# Create your tests here.
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.events.constants import (
    CapacityType,
    EventFormat,
    EventStatus,
    ParticipationType,
)
from apps.events.models import Category, Event
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration


User = get_user_model()


class OrganizerDashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.organizer = self._create_user(
            "organizer@example.test",
            "+221770000001",
        )
        self.organizer.add_role(ROLE_ORGANIZER)

        self.other_organizer = self._create_user(
            "other-organizer@example.test",
            "+221770000002",
        )
        self.other_organizer.add_role(ROLE_ORGANIZER)

        self.category = Category.objects.create(name="Dashboard Test")

        self.event = self._create_event(
            organizer=self.organizer,
            title="Mon événement",
            capacity_type=CapacityType.LIMITED,
            capacity_limit=10,
        )
        self.other_event = self._create_event(
            organizer=self.other_organizer,
            title="Événement d’un autre organisateur",
            capacity_type=CapacityType.UNLIMITED,
            capacity_limit=None,
        )

        pending_participant = self._create_user(
            "pending@example.test",
            "+221770000003",
        )
        confirmed_participant = self._create_user(
            "confirmed@example.test",
            "+221770000004",
        )
        cancelled_participant = self._create_user(
            "cancelled@example.test",
            "+221770000005",
        )
        other_event_participant = self._create_user(
            "other-event@example.test",
            "+221770000006",
        )

        self._create_registration(
            event=self.event,
            participant=pending_participant,
            reference="EVF-REG-2026-PEND01",
            status=RegistrationStatus.PENDING,
        )
        self._create_registration(
            event=self.event,
            participant=confirmed_participant,
            reference="EVF-REG-2026-CONF01",
            status=RegistrationStatus.CONFIRMED,
        )
        self._create_registration(
            event=self.event,
            participant=cancelled_participant,
            reference="EVF-REG-2026-CANC01",
            status=RegistrationStatus.CANCELLED,
        )
        self._create_registration(
            event=self.other_event,
            participant=other_event_participant,
            reference="EVF-REG-2026-OTHER1",
            status=RegistrationStatus.CONFIRMED,
        )

    @staticmethod
    def _create_user(email, phone):
        return User.objects.create_user(
            email=email,
            password="Test-Password-123!",
            first_name="Test",
            last_name="User",
            phone=phone,
        )

    def _create_event(
        self,
        *,
        organizer,
        title,
        capacity_type,
        capacity_limit,
    ):
        start_at = timezone.now() + timedelta(days=2)

        return Event.objects.create(
            organizer=organizer,
            category=self.category,
            title=title,
            short_description="Description courte de test",
            description="Description complète de test",
            format=EventFormat.IN_PERSON,
            participation_type=ParticipationType.PAID,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            capacity_type=capacity_type,
            capacity_limit=capacity_limit,
            status=EventStatus.PUBLISHED,
        )

    @staticmethod
    def _create_registration(*, event, participant, reference, status):
        return Registration.objects.create(
            event=event,
            participant=participant,
            reference=reference,
            status=status,
        )

    def test_organizer_dashboard_is_scoped_and_calculates_capacity(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.get(reverse("dashboards:organizer"))

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]

        self.assertEqual(data["summary"]["total_events"], 1)
        self.assertEqual(data["summary"]["total_registrations"], 3)
        self.assertEqual(data["summary"]["active_registrations"], 2)
        self.assertEqual(data["summary"]["pending_registrations"], 1)
        self.assertEqual(data["summary"]["confirmed_registrations"], 1)
        self.assertEqual(data["summary"]["cancelled_registrations"], 1)
        self.assertEqual(data["summary"]["active_unique_participants"], 2)

        self.assertEqual(len(data["upcoming_events"]), 1)
        upcoming_event = data["upcoming_events"][0]
        self.assertEqual(upcoming_event["title"], "Mon événement")
        self.assertEqual(upcoming_event["capacity"]["occupied"], 2)
        self.assertEqual(upcoming_event["capacity"]["remaining"], 8)
        self.assertEqual(upcoming_event["capacity"]["fill_rate"], 20.0)

        self.assertFalse(data["payment_statistics_available"])
        self.assertIsNone(data["financial_statistics"])

    def test_non_organizer_cannot_view_organizer_dashboard(self):
        participant = self._create_user(
            "not-organizer@example.test",
            "+221770000007",
        )
        self.client.force_authenticate(user=participant)

        response = self.client.get(reverse("dashboards:organizer"))

        self.assertEqual(response.status_code, 403)

class ParticipantDashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.participant = self._create_user(
            "participant-dashboard@example.test",
            "+221770000011",
            ROLE_PARTICIPANT,
        )
        self.other_participant = self._create_user(
            "other-participant@example.test",
            "+221770000012",
            ROLE_PARTICIPANT,
        )
        self.organizer = self._create_user(
            "organizer-dashboard-participant-test@example.test",
            "+221770000013",
            ROLE_ORGANIZER,
        )

        self.category = Category.objects.create(name="Participant Dashboard Test")
        now = timezone.now()

        self.online_event = self._create_online_event(
            title="Événement en ligne confirmé",
            start_at=now + timedelta(days=3),
        )
        self.pending_event = self._create_online_event(
            title="Événement en ligne en attente",
            start_at=now + timedelta(days=4),
        )

        Registration.objects.create(
            event=self.online_event,
            participant=self.participant,
            reference="EVF-REG-2026-PART01",
            status=RegistrationStatus.CONFIRMED,
        )
        Registration.objects.create(
            event=self.online_event,
            participant=self.other_participant,
            reference="EVF-REG-2026-OTHER1",
            status=RegistrationStatus.CONFIRMED,
        )
        Registration.objects.create(
            event=self.pending_event,
            participant=self.participant,
            reference="EVF-REG-2026-PEND01",
            status=RegistrationStatus.PENDING,
        )

    @staticmethod
    def _create_user(email, phone, role):
        user = User.objects.create_user(
            email=email,
            password="Test-Password-123!",
            first_name="Test",
            last_name="Participant",
            phone=phone,
        )
        user.add_role(role)
        return user

    def _create_online_event(self, *, title, start_at):
        return Event.objects.create(
            organizer=self.organizer,
            category=self.category,
            title=title,
            short_description="Description courte de test",
            description="Description complète de test",
            format=EventFormat.ONLINE,
            participation_type=ParticipationType.PAID,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            online_platform="Zoom",
            access_url="https://meeting.example.test/private-room",
            capacity_type=CapacityType.UNLIMITED,
            capacity_limit=None,
            status=EventStatus.PUBLISHED,
        )

    def test_dashboard_only_returns_own_registrations_and_protects_access_url(self):
        self.client.force_authenticate(user=self.participant)

        response = self.client.get(reverse("dashboards:participant"))

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]

        self.assertEqual(data["summary"]["total_registrations"], 2)
        self.assertEqual(data["summary"]["confirmed_registrations"], 1)
        self.assertEqual(data["summary"]["pending_registrations"], 1)
        self.assertEqual(data["summary"]["upcoming_events"], 2)

        registrations = {
            item["reference"]: item
            for item in data["upcoming_registrations"]
        }

        confirmed = registrations["EVF-REG-2026-PART01"]
        pending = registrations["EVF-REG-2026-PEND01"]

        self.assertEqual(
            confirmed["access_url"],
            "https://meeting.example.test/private-room",
        )
        self.assertIsNone(pending["access_url"])
        self.assertNotIn("access_url", confirmed["event"])
        self.assertEqual(len(data["recent_registrations"]), 2)

    def test_non_participant_cannot_view_participant_dashboard(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.get(reverse("dashboards:participant"))

        self.assertEqual(response.status_code, 403)
class AdminDashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin = self._create_user(
            "admin-dashboard@example.test",
            "+221770000021",
            is_staff=True,
        )
        self.participant = self._create_user(
            "participant-admin-dashboard@example.test",
            "+221770000022",
            role=ROLE_PARTICIPANT,
        )
        self.organizer = self._create_user(
            "organizer-admin-dashboard@example.test",
            "+221770000023",
            role=ROLE_ORGANIZER,
        )
        self.inactive_user = self._create_user(
            "inactive-admin-dashboard@example.test",
            "+221770000024",
            is_active=False,
        )

        self.category = Category.objects.create(name="Admin Dashboard Test")
        start_at = timezone.now() + timedelta(days=3)

        self.event = Event.objects.create(
            organizer=self.organizer,
            category=self.category,
            title="Événement global",
            short_description="Description courte de test",
            description="Description complète de test",
            format=EventFormat.IN_PERSON,
            participation_type=ParticipationType.FREE,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            capacity_type=CapacityType.UNLIMITED,
            capacity_limit=None,
            status=EventStatus.PUBLISHED,
        )

        Registration.objects.create(
            event=self.event,
            participant=self.participant,
            reference="EVF-REG-2026-ADMIN1",
            status=RegistrationStatus.CONFIRMED,
        )

    @staticmethod
    def _create_user(
        email,
        phone,
        *,
        role=None,
        is_active=True,
        is_staff=False,
    ):
        user = User.objects.create_user(
            email=email,
            password="Test-Password-123!",
            first_name="Test",
            last_name="Dashboard",
            phone=phone,
            is_active=is_active,
            is_staff=is_staff,
        )
        if role:
            user.add_role(role)
        return user

    def test_admin_dashboard_returns_global_summary(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("dashboards:admin"))

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        summary = data["summary"]

        self.assertEqual(summary["total_users"], 4)
        self.assertEqual(summary["active_users"], 3)
        self.assertEqual(summary["inactive_users"], 1)
        self.assertEqual(summary["participant_users"], 1)
        self.assertEqual(summary["organizer_users"], 1)
        self.assertEqual(summary["admin_users"], 1)

        self.assertEqual(summary["total_events"], 1)
        self.assertEqual(summary["published_events"], 1)
        self.assertEqual(summary["upcoming_events"], 1)

        self.assertEqual(summary["total_registrations"], 1)
        self.assertEqual(summary["confirmed_registrations"], 1)
        self.assertEqual(summary["attended_registrations"], 0)
        self.assertEqual(summary["attendance_rate"], 0.0)

        self.assertEqual(len(data["recent_events"]), 1)
        self.assertEqual(len(data["recent_users"]), 4)
        self.assertFalse(data["payment_statistics_available"])
        self.assertIsNone(data["financial_statistics"])
        self.assertIsNone(data["alerts"])

    def test_non_admin_cannot_view_admin_dashboard(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.get(reverse("dashboards:admin"))

        self.assertEqual(response.status_code, 403)