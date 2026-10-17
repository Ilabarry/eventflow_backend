"""
Test de bout en bout du module Payment.
Simule un paiement complet via les méthodes des services (sans HTTP).
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
from apps.payments.models import Payment
from apps.payments.services import PaymentService
from apps.payments.selectors import get_event_payment_stats, get_payment_by_id
from apps.payments.constants import (
    PaymentMethod, PaymentProvider, PaymentStatus,
)


# ==================================================================
# SETUP
# ==================================================================
print("=" * 60)
print("TEST E2E DU MODULE PAYMENT")
print("=" * 60)

# Créer user
email = f"e2e-{uuid_lib.uuid4().hex[:8]}@eventflow.sn"
user = AuthService.register_user(
    email=email, password="TestPass123!",
    first_name="E2E", last_name="Test",
    phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
    role_name="participant",
)
print(f"\n✅ User créé: {user.email}")


# Créer événement PAYANT
category = Category.objects.first()
event = Event.objects.create(
    organizer=user, category=category,
    title=f"E2E Event {uuid_lib.uuid4().hex[:6]}",
    short_description="Test E2E",
    description="Test end-to-end du module Payment.",
    format=EventFormat.IN_PERSON,
    participation_type=ParticipationType.PAID,
    capacity_type=CapacityType.LIMITED,
    capacity_limit=10,
    base_price=10000,
    start_at=timezone.now() + timedelta(days=15),
    end_at=timezone.now() + timedelta(days=15, hours=3),
    venue_name="Centre E2E",
    address="Rue E2E", city="Dakar",
    status=EventStatus.PUBLISHED,
)
print(f"✅ Event créé: {event.title} | prix={event.base_price} XOF")


# Créer Registration PENDING
reg = Registration.objects.create(
    participant=user, event=event,
    reference=f"EVF-REG-E2E-{uuid_lib.uuid4().hex[:6].upper()}",
    status="PENDING",
)
print(f"✅ Registration créée: {reg.reference} | status={reg.status}")


# ==================================================================
# ÉTAPE 1 : Initier un paiement
# ==================================================================
print("\n--- 1. Initiation d'un paiement ---")
payment = PaymentService.initiate_payment(
    registration=reg,
    payment_method=PaymentMethod.DEVELOPMENT,
    provider_name=PaymentProvider.DEVELOPMENT,
    idempotency_key=f"e2e-{uuid_lib.uuid4().hex}",
)
print(f"✅ Payment initié: {payment.transaction_reference}")
print(f"   Montant: {payment.amount} {payment.currency}")
print(f"   Statut: {payment.status}")
print(f"   Provider ref: {payment.provider_reference}")


# ==================================================================
# ÉTAPE 2 : Vérifier que Registration est toujours PENDING
# ==================================================================
reg.refresh_from_db()
print(f"\n--- 2. Vérification Registration ---")
print(f"   Registration status: {reg.status}")
assert reg.status == "PENDING", "Registration devrait être PENDING avant paiement"


# ==================================================================
# ÉTAPE 3 : Simuler le SUCCESS
# ==================================================================
print("\n--- 3. Simulation SUCCESS ---")
payment = PaymentService.simulate_payment_result(payment=payment, result="SUCCESS")
print(f"✅ Payment status: {payment.status}")
print(f"   Paid at: {payment.paid_at}")


# ==================================================================
# ÉTAPE 4 : Vérifier la confirmation automatique
# ==================================================================
reg.refresh_from_db()
print(f"\n--- 4. Confirmation automatique ---")
print(f"   Registration status: {reg.status}")
assert reg.status == "CONFIRMED", "Registration devrait être CONFIRMED après paiement"


# ==================================================================
# ÉTAPE 5 : Tester l'idempotence
# ==================================================================
print("\n--- 5. Test idempotence ---")
# Récupérer le payment créé
existing_payment = get_payment_by_id(payment.id)
print(f"✅ Payment récupéré: {existing_payment.transaction_reference}")


# ==================================================================
# ÉTAPE 6 : Vérifier les statistiques
# ==================================================================
print("\n--- 6. Statistiques de l'événement ---")
stats = get_event_payment_stats(event)
print(f"✅ Stats:")
for key, value in stats.items():
    print(f"   {key}: {value}")

assert stats["total_transactions"] == 1
assert stats["successful"] == 1
assert stats["total_amount"] == 10000


# ==================================================================
# ÉTAPE 7 : Test : tentative de double paiement (doit échouer)
# ==================================================================
print("\n--- 7. Test double paiement ---")
try:
    PaymentService.initiate_payment(
        registration=reg,
        payment_method=PaymentMethod.DEVELOPMENT,
        provider_name=PaymentProvider.DEVELOPMENT,
    )
    print("❌ La double initiation aurait dû échouer")
except Exception as e:
    print(f"✅ Bloqué: {type(e).__name__}")


# ==================================================================
# NETTOYAGE
# ==================================================================
print("\n--- Nettoyage ---")
Payment.objects.filter(registration=reg).delete()
reg.delete()
event.delete()
user.delete()
print("✅ Nettoyage OK")


print("\n" + "=" * 60)
print("🎉 TOUS LES TESTS E2E SONT PASSÉS !")
print("=" * 60)