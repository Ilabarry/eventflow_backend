
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.accounts.models import User
from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.certificates.constants import CertificateStatus
from apps.certificates.services import CertificateService
from apps.events.constants import EventStatus
from apps.events.models import Category, Event
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from common.exceptions.business import AttendanceRequired


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher"
    ],
)
class CertificateServiceTests(TestCase):
    """Tests des règles métier du module Certificates."""

    def setUp(self):
        super().setUp()
        self._prepare_test_data()

    def _prepare_test_data(self):
        """Crée les données nécessaires dans la base de test."""

        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

        self._media_override = override_settings(
            MEDIA_ROOT=self.temp_media.name
        )
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)

        self.organizer = User.objects.create_user(
            email="organisateur.certificat@test.com",
            password="TestPass2026",
            first_name="Test",
            last_name="Organisateur",
            phone="+221770000001",
        )
        self.organizer.add_role(ROLE_ORGANIZER)

        self.participant = User.objects.create_user(
            email="participant.certificat@test.com",
            password="TestPass2026",
            first_name="Awa",
            last_name="Test",
            phone="+221770000002",
        )
        self.participant.add_role(ROLE_PARTICIPANT)

        category = Category.objects.create(
            name="Tests certificats"
        )

        end_at = timezone.now() - timedelta(hours=1)
        start_at = end_at - timedelta(hours=2)

        self.event = Event.objects.create(
            organizer=self.organizer,
            category=category,
            title="Événement de test",
            short_description="Résumé du test",
            description="Événement créé pour tester les attestations.",
            start_at=start_at,
            end_at=end_at,
            venue_name="Salle de test",
            address="Adresse de test",
            city="Dakar",
            status=EventStatus.COMPLETED,
        )

        self.registration = Registration.objects.create(
            participant=self.participant,
            event=self.event,
            reference="EVF-REG-CERT-000001",
            status=RegistrationStatus.CONFIRMED,
        )

    def _add_presence(self):
        """Enregistre la présence du participant."""

        Attendance.objects.create(
            registration=self.registration,
            status=AttendanceStatus.PRESENT,
            checked_in_at=timezone.now() - timedelta(minutes=30),
            check_in_method=CheckInMethod.MANUAL,
            recorded_by=self.organizer,
        )

    def test_generation_refusee_sans_presence(self):
        """La génération est refusée si le participant est absent."""

        with self.assertRaises(AttendanceRequired):
            CertificateService.generate_certificate(
                self.registration
            )

    def test_generation_reussie_avec_presence(self):
        """Un certificat est généré après confirmation de présence."""

        self._add_presence()

        certificate = CertificateService.generate_certificate(
            self.registration
        )

        self.assertEqual(
            certificate.status,
            CertificateStatus.ISSUED,
        )
        self.assertTrue(certificate.pdf_file)
        self.assertGreater(certificate.pdf_file.size, 0)
        self.assertTrue(certificate.reference.startswith("CERT-"))

    def test_revocation_certificat_emis(self):
        """Un certificat émis peut être révoqué."""

        self._add_presence()

        certificate = CertificateService.generate_certificate(
            self.registration
        )

        certificate = CertificateService.revoke_certificate(
            certificate=certificate,
            revoked_by=self.organizer,
        )
        certificate.refresh_from_db()

        self.assertEqual(
            certificate.status,
            CertificateStatus.REVOKED,
        )
        self.assertIsNotNone(certificate.revoked_at)
        self.assertEqual(certificate.revoked_by, self.organizer)


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher"
    ],
)
class CertificateVerificationAPITests(TestCase):
    """Tests HTTP de l'API publique de vérification."""

    def setUp(self):
        super().setUp()

        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

        self._media_override = override_settings(
            MEDIA_ROOT=self.temp_media.name
        )
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)

        self.client = APIClient()

        self.organizer = User.objects.create_user(
            email="organisateur.api.certificat@test.com",
            password="TestPass2026",
            first_name="Test",
            last_name="Organisateur",
            phone="+221770000011",
        )
        self.organizer.add_role(ROLE_ORGANIZER)

        self.participant = User.objects.create_user(
            email="participant.api.certificat@test.com",
            password="TestPass2026",
            first_name="Awa",
            last_name="Test",
            phone="+221770000012",
        )
        self.participant.add_role(ROLE_PARTICIPANT)

        category = Category.objects.create(
            name="Tests API certificats"
        )

        end_at = timezone.now() - timedelta(hours=1)
        start_at = end_at - timedelta(hours=2)

        self.event = Event.objects.create(
            organizer=self.organizer,
            category=category,
            title="Événement API de test",
            short_description="Résumé du test",
            description="Événement créé pour tester l'API.",
            start_at=start_at,
            end_at=end_at,
            venue_name="Salle de test",
            address="Adresse de test",
            city="Dakar",
            status=EventStatus.COMPLETED,
        )

        self.registration = Registration.objects.create(
            participant=self.participant,
            event=self.event,
            reference="EVF-REG-API-CERT-000001",
            status=RegistrationStatus.CONFIRMED,
        )

    def _creer_certificat_valide(self):
        """Crée un certificat émis pour les tests API."""

        Attendance.objects.create(
            registration=self.registration,
            status=AttendanceStatus.PRESENT,
            checked_in_at=timezone.now() - timedelta(minutes=30),
            check_in_method=CheckInMethod.MANUAL,
            recorded_by=self.organizer,
        )

        return CertificateService.generate_certificate(
            self.registration
        )

    def test_verification_certificat_valide(self):
        """L'API confirme qu'un certificat émis est valide."""

        certificate = self._creer_certificat_valide()

        response = self.client.get(
            f"/api/certificates/verify/"
            f"{certificate.verification_code}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["data"]["valid"])
        self.assertEqual(
            response.data["data"]["reference"],
            certificate.reference,
        )

    def test_verification_certificat_revoque(self):
        """L'API indique qu'un certificat révoqué est invalide."""

        certificate = self._creer_certificat_valide()

        CertificateService.revoke_certificate(
            certificate=certificate,
            revoked_by=self.organizer,
        )

        response = self.client.get(
            f"/api/certificates/verify/"
            f"{certificate.verification_code}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(response.data["data"]["valid"])
        self.assertIn(
            "révoqué",
            response.data["data"]["reason"].lower(),
        )

    def test_verification_code_inexistant(self):
        """L'API refuse un code de vérification inconnu."""

        response = self.client.get(
            "/api/certificates/verify/CODE-INEXISTANT-123/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(response.data["data"]["valid"])
