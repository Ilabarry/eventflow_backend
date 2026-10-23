"""Tests de la liste « Mes tickets » (GET /api/tickets/my/)."""

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
from apps.tickets.models import Ticket


User = get_user_model()


class MyTicketsCoverImageAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.participant = self._create_user(
            "ticket-owner@example.test", "+221770000101", ROLE_PARTICIPANT,
        )
        self.other_participant = self._create_user(
            "ticket-other@example.test", "+221770000102", ROLE_PARTICIPANT,
        )
        self.organizer = self._create_user(
            "ticket-organizer@example.test", "+221770000103", ROLE_ORGANIZER,
        )
        self.category = Category.objects.create(name="Tickets Test")

        event_with_image = self._create_event("Forum avec image")
        event_with_image.cover_image = "events/covers/forum.jpg"
        event_with_image.save(update_fields=["cover_image"])
        event_without_image = self._create_event("Atelier sans image")

        self._create_ticket(event_with_image, "EVF-TKT-TEST-0001")
        self._create_ticket(event_without_image, "EVF-TKT-TEST-0002")

    @staticmethod
    def _create_user(email, phone, role):
        user = User.objects.create_user(
            email=email,
            password="Test-Password-123!",
            first_name="Test",
            last_name="Ticket",
            phone=phone,
        )
        user.add_role(role)
        return user

    def _create_event(self, title):
        start_at = timezone.now() + timedelta(days=5)
        return Event.objects.create(
            organizer=self.organizer,
            category=self.category,
            title=title,
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

    def _create_ticket(self, event, reference):
        registration = Registration.objects.create(
            event=event,
            participant=self.participant,
            reference=reference.replace("TKT", "REG"),
            status=RegistrationStatus.CONFIRMED,
        )
        return Ticket.objects.create(registration=registration, reference=reference)

    def test_my_tickets_returns_absolute_cover_image_url_or_null(self):
        self.client.force_authenticate(user=self.participant)

        response = self.client.get(reverse("tickets:ticket-my"))

        self.assertEqual(response.status_code, 200)
        tickets = {
            item["reference"]: item
            for item in response.data["data"]["results"]
        }
        self.assertEqual(
            tickets["EVF-TKT-TEST-0001"]["event_cover_image"],
            "http://testserver/media/events/covers/forum.jpg",
        )
        self.assertIsNone(tickets["EVF-TKT-TEST-0002"]["event_cover_image"])

    def test_my_tickets_only_lists_own_tickets(self):
        self.client.force_authenticate(user=self.other_participant)

        response = self.client.get(reverse("tickets:ticket-my"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 0)

    def test_anonymous_user_cannot_list_tickets(self):
        response = self.client.get(reverse("tickets:ticket-my"))

        self.assertEqual(response.status_code, 401)
