"""
Tests du module Attendance — phase 2 (modèle + service).

Lancer :
    python manage.py test apps.attendance

Django crée une base de test temporaire (test_eventflow_db),
exécute les tests, puis la supprime : vos vraies données ne sont
jamais touchées.
"""

import threading
from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.constants import ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.accounts.models import User
from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.attendance.services import AttendanceService
from apps.events.constants import EventStatus
from apps.events.models import Category, Event
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from common.exceptions.business import (
    AlreadyCheckedIn,
    AttendanceRegistrationNotFound,
    CheckInNotOpen,
    EventCancelled,
    EventCompleted,
    EventNotPublished,
    RegistrationNotEligibleForCheckIn,
    UnauthorizedEventAccess,
)


# Hachage rapide des mots de passe, UNIQUEMENT pendant les tests :
# le hachage réel (PBKDF2) est volontairement lent pour la sécurité,
# ce qui ralentirait inutilement chaque création d'utilisateur de test.
FAST_HASHER = override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)


# ==================================================================
# OUTILS DE CRÉATION DE DONNÉES DE TEST
# ==================================================================
class AttendanceTestDataMixin:
    """Crée des utilisateurs, un événement en cours et une inscription."""

    _phone_counter = 0

    @classmethod
    def make_user(cls, email, role=None, **extra):
        cls._phone_counter += 1
        user = User.objects.create_user(
            email=email,
            password="TestPass2026",
            first_name="Test",
            last_name=email.split("@")[0],
            phone=f"+2299000{cls._phone_counter:04d}",
            **extra,
        )
        if role:
            user.add_role(role)
        return user

    @staticmethod
    def make_event(organizer, category, *, starts_in=timedelta(hours=-1),
                   duration=timedelta(hours=3), status=EventStatus.PUBLISHED):
        start = timezone.now() + starts_in
        return Event.objects.create(
            organizer=organizer,
            category=category,
            title="Conférence test",
            short_description="Résumé",
            description="Description",
            start_at=start,
            end_at=start + duration,
            venue_name="Salle A",
            address="Rue 1",
            city="Cotonou",
            status=status,
        )

    _ref_counter = 0

    @classmethod
    def make_registration(cls, participant, event, status=RegistrationStatus.CONFIRMED):
        cls._ref_counter += 1
        return Registration.objects.create(
            participant=participant,
            event=event,
            reference=f"EVF-REG-TEST-{cls._ref_counter:06d}",
            status=status,
        )

    def setUp(self):
        self.organizer = self.make_user("orga@test.com", ROLE_ORGANIZER)
        self.other_organizer = self.make_user("autre.orga@test.com", ROLE_ORGANIZER)
        self.admin = self.make_user("admin@test.com", is_staff=True)
        self.participant = self.make_user("awa@test.com", ROLE_PARTICIPANT)
        self.category = Category.objects.create(name="Tech")
        self.event = self.make_event(self.organizer, self.category)
        self.registration = self.make_registration(self.participant, self.event)


# ==================================================================
# MODÈLE : contraintes en base
# ==================================================================
@FAST_HASHER
class AttendanceModelTests(AttendanceTestDataMixin, TestCase):

    def test_uuid_primary_key(self):
        attendance = Attendance.objects.create(
            registration=self.registration,
            status=AttendanceStatus.PRESENT,
            checked_in_at=timezone.now(),
            check_in_method=CheckInMethod.MANUAL,
        )
        self.assertEqual(len(str(attendance.id)), 36)
        self.assertEqual(self.registration.attendance, attendance)

    def test_unique_attendance_per_registration(self):
        """La base refuse une 2e fiche pour la même inscription."""
        Attendance.objects.create(registration=self.registration, status=AttendanceStatus.ABSENT)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(registration=self.registration, status=AttendanceStatus.ABSENT)

    def test_present_requires_check_in_time_and_method(self):
        """La base refuse un PRESENT sans heure ni méthode."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(registration=self.registration, status=AttendanceStatus.PRESENT)

    def test_absent_cannot_have_check_in_method(self):
        """La base refuse un ABSENT avec une méthode de check-in."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    registration=self.registration,
                    status=AttendanceStatus.ABSENT,
                    check_in_method=CheckInMethod.MANUAL,
                )


# ==================================================================
# SERVICE : check-in
# ==================================================================
@FAST_HASHER
class CheckInServiceTests(AttendanceTestDataMixin, TestCase):

    def test_check_in_success(self):
        attendance = AttendanceService.check_in(
            registration_id=self.registration.id, performed_by=self.organizer,
        )
        self.assertEqual(attendance.status, AttendanceStatus.PRESENT)
        self.assertEqual(attendance.check_in_method, CheckInMethod.MANUAL)
        self.assertIsNotNone(attendance.checked_in_at)
        self.assertEqual(attendance.recorded_by, self.organizer)

    def test_double_check_in_is_refused(self):
        AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)
        with self.assertRaises(AlreadyCheckedIn):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_unknown_registration(self):
        import uuid
        with self.assertRaises(AttendanceRegistrationNotFound):
            AttendanceService.check_in(registration_id=uuid.uuid4(), performed_by=self.organizer)

    def test_cancelled_registration_is_refused(self):
        self.registration.status = RegistrationStatus.CANCELLED
        self.registration.save()
        with self.assertRaises(RegistrationNotEligibleForCheckIn):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)

    def test_pending_registration_is_refused(self):
        self.registration.status = RegistrationStatus.PENDING
        self.registration.save()
        with self.assertRaises(RegistrationNotEligibleForCheckIn):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)

    def test_draft_event_is_refused(self):
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.DRAFT)
        with self.assertRaises(EventNotPublished):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)

    def test_cancelled_event_is_refused(self):
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.CANCELLED)
        with self.assertRaises(EventCancelled):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)

    def test_completed_event_is_refused(self):
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.COMPLETED)
        with self.assertRaises(EventCompleted):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)

    @override_settings(ATTENDANCE_CHECK_IN_OPENS_BEFORE_MINUTES=120)
    def test_check_in_too_early(self):
        """Événement dans 5 h, check-in ouvert 2 h avant : trop tôt."""
        event = self.make_event(self.organizer, self.category, starts_in=timedelta(hours=5))
        registration = self.make_registration(self.participant, event)
        with self.assertRaises(CheckInNotOpen):
            AttendanceService.check_in(registration_id=registration.id, performed_by=self.organizer)

    @override_settings(ATTENDANCE_CHECK_IN_OPENS_BEFORE_MINUTES=120)
    def test_check_in_allowed_one_hour_before_start(self):
        event = self.make_event(self.organizer, self.category, starts_in=timedelta(hours=1))
        registration = self.make_registration(self.participant, event)
        attendance = AttendanceService.check_in(registration_id=registration.id, performed_by=self.organizer)
        self.assertTrue(attendance.is_present)

    def test_check_in_after_event_end(self):
        event = self.make_event(
            self.organizer, self.category,
            starts_in=timedelta(hours=-5), duration=timedelta(hours=2),
        )
        registration = self.make_registration(self.participant, event)
        with self.assertRaises(CheckInNotOpen):
            AttendanceService.check_in(registration_id=registration.id, performed_by=self.organizer)

    def test_other_organizer_is_refused(self):
        with self.assertRaises(UnauthorizedEventAccess):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.other_organizer)

    def test_participant_cannot_check_in_himself(self):
        with self.assertRaises(UnauthorizedEventAccess):
            AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.participant)

    def test_admin_can_check_in(self):
        attendance = AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.admin)
        self.assertEqual(attendance.recorded_by, self.admin)

    def test_invalid_method_is_refused(self):
        from common.exceptions.business import BusinessException
        with self.assertRaises(BusinessException):
            AttendanceService.check_in(
                registration_id=self.registration.id, performed_by=self.organizer, method="HACK",
            )

    def test_absent_then_late_arrival_becomes_present(self):
        AttendanceService.mark_absent(registration_id=self.registration.id, performed_by=self.organizer)
        attendance = AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)
        self.assertTrue(attendance.is_present)
        self.assertEqual(Attendance.objects.count(), 1)


# ==================================================================
# SERVICE : absence
# ==================================================================
@FAST_HASHER
class MarkAbsentServiceTests(AttendanceTestDataMixin, TestCase):

    def test_mark_absent_success(self):
        attendance = AttendanceService.mark_absent(
            registration_id=self.registration.id, performed_by=self.organizer,
        )
        self.assertEqual(attendance.status, AttendanceStatus.ABSENT)
        self.assertIsNone(attendance.checked_in_at)
        self.assertIsNone(attendance.check_in_method)

    def test_mark_absent_is_idempotent(self):
        first = AttendanceService.mark_absent(registration_id=self.registration.id, performed_by=self.organizer)
        second = AttendanceService.mark_absent(registration_id=self.registration.id, performed_by=self.organizer)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_present_participant_cannot_be_marked_absent(self):
        AttendanceService.check_in(registration_id=self.registration.id, performed_by=self.organizer)
        with self.assertRaises(AlreadyCheckedIn):
            AttendanceService.mark_absent(registration_id=self.registration.id, performed_by=self.organizer)

    def test_mark_absent_before_start_is_refused(self):
        event = self.make_event(self.organizer, self.category, starts_in=timedelta(minutes=30))
        registration = self.make_registration(self.participant, event)
        with self.assertRaises(CheckInNotOpen):
            AttendanceService.mark_absent(registration_id=registration.id, performed_by=self.organizer)

    def test_mark_absent_allowed_on_completed_event(self):
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.COMPLETED)
        attendance = AttendanceService.mark_absent(
            registration_id=self.registration.id, performed_by=self.organizer,
        )
        self.assertTrue(attendance.is_absent)

    def test_other_organizer_cannot_mark_absent(self):
        with self.assertRaises(UnauthorizedEventAccess):
            AttendanceService.mark_absent(
                registration_id=self.registration.id, performed_by=self.other_organizer,
            )


# ==================================================================
# CONCURRENCE : deux check-ins simultanés
# ==================================================================
@FAST_HASHER
class CheckInConcurrencyTests(AttendanceTestDataMixin, TransactionTestCase):
    """
    TransactionTestCase : chaque thread doit voir les données réellement
    enregistrées en base (TestCase garderait tout dans une transaction
    invisible pour les autres connexions).
    """

    def test_two_simultaneous_check_ins_create_one_attendance(self):
        barrier = threading.Barrier(2)
        results = []

        def scan():
            try:
                barrier.wait()  # les deux threads partent en même temps
                AttendanceService.check_in(
                    registration_id=self.registration.id, performed_by=self.organizer,
                )
                results.append("created")
            except AlreadyCheckedIn:
                results.append("conflict")
            finally:
                connection.close()  # chaque thread a sa propre connexion

        threads = [threading.Thread(target=scan) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(results), ["conflict", "created"])
        self.assertEqual(Attendance.objects.filter(registration=self.registration).count(), 1)
