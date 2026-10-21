"""
Test temporaire de génération PDF + QR.
"""

import os
import uuid as uuid_lib
from datetime import timedelta

import django
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventflow_backend.settings")
django.setup()

from apps.accounts.services import AuthService
from apps.events.models import Event, Category
from apps.events.constants import (
    EventFormat, EventStatus, ParticipationType, CapacityType,
)
from apps.registrations.models import Registration
from apps.certificates.models import Certificate
from apps.certificates.constants import CertificateStatus
from apps.certificates.pdf import generate_certificate_pdf
from apps.certificates.qr import build_verify_url, generate_qr_image_bytes


# Setup
organizer = AuthService.register_user(
    email=f"org-{uuid_lib.uuid4().hex[:8]}@eventflow.sn",
    password="TestPass123!",
    first_name="Orga", last_name="Test",
    phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
    role_name="organisateur",
)
participant = AuthService.register_user(
    email=f"part-{uuid_lib.uuid4().hex[:8]}@eventflow.sn",
    password="TestPass123!",
    first_name="Ila", last_name="Barry",
    phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
    role_name="participant",
)

category = Category.objects.first() or Category.objects.create(name="Test", description="Test")
event = Event.objects.create(
    organizer=organizer, category=category,
    title="Tech Meetup Dakar",
    short_description="Rencontre tech",
    description="Description",
    format=EventFormat.IN_PERSON,
    participation_type=ParticipationType.FREE,
    capacity_type=CapacityType.UNLIMITED,
    start_at=timezone.now() - timedelta(days=2),
    end_at=timezone.now() - timedelta(days=2, hours=-3),
    venue_name="Centre", address="Rue", city="Dakar",
    status=EventStatus.COMPLETED,
)

reg = Registration.objects.create(
    participant=participant, event=event,
    reference=f"EVF-REG-CERT-{uuid_lib.uuid4().hex[:6].upper()}",
    status="CONFIRMED",
)


# 1. Test URL de vérification
print("\n[TEST 1] URL de vérification")
url = build_verify_url("abc123def456")
print(f"  ✅ URL: {url}")


# 2. Test génération QR
print("\n[TEST 2] Génération QR")
qr_bytes = generate_qr_image_bytes("abc123def456")
print(f"  ✅ QR généré: {len(qr_bytes)} bytes")


# 3. Test génération PDF
print("\n[TEST 3] Génération PDF")
cert = Certificate.objects.create(
    registration=reg,
    reference=f"CERT-2026-{uuid_lib.uuid4().hex[:6].upper()}",
    verification_code=uuid_lib.uuid4().hex,
    status=CertificateStatus.ISSUED,
)

pdf_bytes = generate_certificate_pdf(cert)
print(f"  ✅ PDF généré: {len(pdf_bytes)} bytes")

# Sauvegarde pour vérification visuelle
with open("test_certificate.pdf", "wb") as f:
    f.write(pdf_bytes)
print(f"  ✅ PDF sauvegardé: test_certificate.pdf")


# Nettoyage
print("\n[NETTOYAGE]")
cert.delete()
reg.delete()
event.delete()
organizer.delete()
participant.delete()
print("  ✅ Nettoyage OK")


print("\n🎉 Tests PDF et QR passés !")
print("📄 Ouvre test_certificate.pdf pour vérifier visuellement.")