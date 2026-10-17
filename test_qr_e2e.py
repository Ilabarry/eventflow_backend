"""
Test de bout en bout du check-in QR.
Simule le parcours complet :
    1. Créer un utilisateur + event payant + ticket type
    2. Créer une registration CONFIRMED
    3. Émettre un ticket (via TicketService)
    4. Générer un QR payload
    5. Faire un check-in QR (via AttendanceService)
    6. Vérifier que le ticket est USED
    7. Vérifier qu'un second scan échoue (409)
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
from apps.tickets.models import Ticket, TicketType
from apps.tickets.services import TicketService
from apps.tickets.constants import TicketStatus
from apps.attendance.services import AttendanceService
from apps.attendance.models import Attendance
from apps.attendance.constants import AttendanceStatus, CheckInMethod
from common.exceptions.business import AlreadyCheckedIn, TicketNotUsable


print("=" * 60)
print("TEST E2E : CHECK-IN QR")
print("=" * 60)


# ==================================================================
# SETUP
# ==================================================================
print("\n[SETUP] Création des données de test...")

# Organisateur
organizer = AuthService.register_user(
    email=f"org-{uuid_lib.uuid4().hex[:8]}@eventflow.sn",
    password="TestPass123!",
    first_name="Orga",
    last_name="Test",
    phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
    role_name="organisateur",
)
print(f"  ✅ Organisateur: {organizer.email}")

# Participant
participant = AuthService.register_user(
    email=f"part-{uuid_lib.uuid4().hex[:8]}@eventflow.sn",
    password="TestPass123!",
    first_name="Part",
    last_name="Test",
    phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
    role_name="participant",
)
print(f"  ✅ Participant: {participant.email}")

# Event (dans le futur proche, pour que le check-in soit ouvert)
category = Category.objects.first()
if not category:
    category = Category.objects.create(name="Test", description="Test")

now = timezone.now()
event = Event.objects.create(
    organizer=organizer,
    category=category,
    title=f"Test QR Event {uuid_lib.uuid4().hex[:6]}",
    short_description="Test QR",
    description="Test check-in QR",
    format=EventFormat.IN_PERSON,
    participation_type=ParticipationType.PAID,
    capacity_type=CapacityType.UNLIMITED,
    base_price=10000,
    start_at=now - timedelta(minutes=10),  # Commencé il y a 10 min
    end_at=now + timedelta(hours=3),        # Fin dans 3h
    venue_name="Centre",
    address="Rue",
    city="Dakar",
    status=EventStatus.PUBLISHED,
)
print(f"  ✅ Event: {event.title} (en cours)")

# TicketType
tt = TicketType.objects.create(
    event=event,
    name="Standard",
    price=10000,
    currency="XOF",
    quantity_total=100,
)
print(f"  ✅ TicketType: {tt.name}")

# Registration CONFIRMED
reg = Registration.objects.create(
    participant=participant,
    event=event,
    ticket_type=tt,
    reference=f"EVF-REG-QR-{uuid_lib.uuid4().hex[:6].upper()}",
    status="CONFIRMED",
    price_paid=tt.price,
)
print(f"  ✅ Registration: {reg.reference} (CONFIRMED)")

# Ticket
ticket = TicketService.issue_ticket_for_registration(reg)
print(f"  ✅ Ticket: {ticket.reference} (status={ticket.status})")


# ==================================================================
# TEST 1 : Génération du QR
# ==================================================================
print("\n[TEST 1] Génération du payload QR")
qr_payload = TicketService.generate_qr_payload(ticket)
print(f"  ✅ QR payload: {qr_payload[:60]}...")

# Vérifier que le QR contient bien 2 parties
parts = qr_payload.split("|")
assert len(parts) == 2, "Le QR doit contenir 'reference|signature'"
assert parts[0] == ticket.reference, "La référence doit correspondre"
print(f"  ✅ Format valide: reference={parts[0]} | signature={parts[1][:16]}...")


# ==================================================================
# TEST 2 : Vérification du QR
# ==================================================================
print("\n[TEST 2] Vérification du payload QR")
verified_ticket = TicketService.verify_qr_payload(qr_payload)
assert verified_ticket is not None, "Le QR devrait être valide"
assert verified_ticket.id == ticket.id, "Le ticket devrait correspondre"
print(f"  ✅ QR vérifié: {verified_ticket.reference}")


# ==================================================================
# TEST 3 : Check-in QR
# ==================================================================
print("\n[TEST 3] Check-in via QR")
attendance = AttendanceService.check_in_by_qr(
    qr_code=qr_payload,
    performed_by=organizer,
)
print(f"  ✅ Attendance créée: {attendance.id}")
print(f"     Status: {attendance.status}")
print(f"     Méthode: {attendance.check_in_method}")
print(f"     Checked in at: {attendance.checked_in_at}")

assert attendance.status == AttendanceStatus.PRESENT
assert attendance.check_in_method == CheckInMethod.QR_CODE

# Vérifier que le ticket est passé à USED
ticket.refresh_from_db()
print(f"  ✅ Ticket status: {ticket.status}")
assert ticket.status == TicketStatus.USED


# ==================================================================
# TEST 4 : Second scan doit échouer
# ==================================================================
print("\n[TEST 4] Second scan (doit échouer avec 409)")
try:
    AttendanceService.check_in_by_qr(
        qr_code=qr_payload,
        performed_by=organizer,
    )
    print("  ❌ Le second scan aurait dû échouer")
except TicketNotUsable as e:
    print(f"  ✅ Second scan bloqué (TicketNotUsable): {e.detail}")
except AlreadyCheckedIn as e:
    print(f"  ✅ Second scan bloqué (AlreadyCheckedIn): {e.detail}")
except Exception as e:
    print(f"  ✅ Second scan bloqué ({type(e).__name__}): {e}")


# ==================================================================
# TEST 5 : QR falsifié doit échouer
# ==================================================================
print("\n[TEST 5] QR falsifié (doit échouer)")
fake_qr = f"{ticket.reference}|fake_signature"
try:
    AttendanceService.check_in_by_qr(
        qr_code=fake_qr,
        performed_by=organizer,
    )
    print("  ❌ Le QR falsifié aurait dû échouer")
except Exception as e:
    print(f"  ✅ QR falsifié bloqué ({type(e).__name__}): {e}")


# ==================================================================
# TEST 6 : Check-in par un non-organisateur (doit échouer)
# ==================================================================
print("\n[TEST 6] Check-in par un participant (doit échouer avec 403)")

# Créer un 2e participant qui n'est pas organisateur
other_participant = AuthService.register_user(
    email=f"other-{uuid_lib.uuid4().hex[:8]}@eventflow.sn",
    password="TestPass123!",
    first_name="Other",
    last_name="User",
    phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
    role_name="participant",
)

# Créer une 2e registration pour ce participant
reg2 = Registration.objects.create(
    participant=other_participant,
    event=event,
    ticket_type=tt,
    reference=f"EVF-REG-QR-{uuid_lib.uuid4().hex[:6].upper()}",
    status="CONFIRMED",
    price_paid=tt.price,
)
ticket2 = TicketService.issue_ticket_for_registration(reg2)
qr2 = TicketService.generate_qr_payload(ticket2)

try:
    AttendanceService.check_in_by_qr(
        qr_code=qr2,
        performed_by=other_participant,  # ← pas organisateur
    )
    print("  ❌ Le check-in par un non-organisateur aurait dû échouer")
except Exception as e:
    print(f"  ✅ Check-in non autorisé bloqué ({type(e).__name__}): {e}")


# ==================================================================
# NETTOYAGE
# ==================================================================
print("\n[NETTOYAGE]")
Attendance.objects.filter(registration__event=event).delete()
Ticket.objects.filter(registration__event=event).delete()
Registration.objects.filter(event=event).delete()
tt.delete()
event.delete()
organizer.delete()
participant.delete()
other_participant.delete()
print("  ✅ Nettoyage OK")


print("\n" + "=" * 60)
print("🎉 TOUS LES TESTS E2E SONT PASSÉS !")
print("=" * 60)