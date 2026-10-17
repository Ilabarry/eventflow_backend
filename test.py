"""
Test de concurrence pour le module Tickets.

Scénario :
    - TicketType avec quantity_total = 1
    - Deux inscriptions simultanées
    - Un seul ticket doit être émis
"""

import os
import threading
import uuid as uuid_lib
from datetime import timedelta

import django
from django.db import connection
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


# ==================================================================
# SETUP
# ==================================================================
print("=" * 60)
print("TEST DE CONCURRENCE — MODULE TICKETS")
print("=" * 60)

# Créer 2 users
users = []
for i in range(2):
    email = f"conc-{i}-{uuid_lib.uuid4().hex[:6]}@eventflow.sn"
    u = AuthService.register_user(
        email=email, password="TestPass123!",
        first_name=f"User{i}", last_name="Test",
        phone=f"+22177{uuid_lib.uuid4().int % 100000000:08d}",
        role_name="participant",
    )
    users.append(u)

print(f"✅ 2 users créés")

# Créer event + ticket type limité à 1
category = Category.objects.first()
event = Event.objects.create(
    organizer=users[0], category=category,
    title=f"Conc Test {uuid_lib.uuid4().hex[:6]}",
    short_description="T", description="T",
    format=EventFormat.IN_PERSON,
    participation_type=ParticipationType.PAID,
    capacity_type=CapacityType.LIMITED,
    capacity_limit=1,
    base_price=10000,
    start_at=timezone.now() + timedelta(days=15),
    end_at=timezone.now() + timedelta(days=15, hours=2),
    venue_name="C", address="R", city="Dakar",
    status=EventStatus.PUBLISHED,
)

tt = TicketType.objects.create(
    event=event, name="VIP",
    price=10000, quantity_total=1,
)
print(f"✅ TicketType créé (quantity_total=1)")

# Créer 2 registrations CONFIRMED
registrations = []
for i, u in enumerate(users):
    reg = Registration.objects.create(
        participant=u, event=event, ticket_type=tt,
        reference=f"EVF-REG-CONC-{i}-{uuid_lib.uuid4().hex[:4].upper()}",
        status="CONFIRMED", price_paid=tt.price,
    )
    registrations.append(reg)
print(f"✅ 2 registrations CONFIRMED créées")


# ==================================================================
# TEST : 2 émissions simultanées
# ==================================================================
print("\n--- Test : 2 émissions simultanées ---")

results = {"success": 0, "error": 0, "errors": []}

def issue_ticket(reg, results):
    """Émet un ticket dans un thread séparé."""
    try:
        ticket = TicketService.issue_ticket_for_registration(reg)
        results["success"] += 1
        print(f"   ✅ Thread réussi: {ticket.reference}")
    except Exception as e:
        results["error"] += 1
        results["errors"].append(type(e).__name__)
        print(f"   ❌ Thread échoué: {type(e).__name__}")
    finally:
        # Fermer la connexion pour éviter les fuites
        connection.close()


# Lancer les 2 threads en parallèle
threads = []
for reg in registrations:
    t = threading.Thread(target=issue_ticket, args=(reg, results))
    threads.append(t)

for t in threads:
    t.start()

for t in threads:
    t.join()


# ==================================================================
# VÉRIFICATION
# ==================================================================
print("\n--- Vérification ---")
total_tickets = Ticket.objects.filter(registration__event=event).count()
tt.refresh_from_db()

print(f"   Tickets émis: {total_tickets}")
print(f"   quantity_sold: {tt.quantity_sold}")
print(f"   quantity_total: {tt.quantity_total}")
print(f"   Succès: {results['success']}")
print(f"   Erreurs: {results['error']}")
print(f"   Types d'erreurs: {results['errors']}")

assert total_tickets == 1, f"❌ Attendu 1 ticket, obtenu {total_tickets}"
assert tt.quantity_sold == 1, f"❌ Attendu quantity_sold=1, obtenu {tt.quantity_sold}"
assert results["success"] == 1, f"❌ Attendu 1 succès, obtenu {results['success']}"
assert results["error"] == 1, f"❌ Attendu 1 erreur, obtenu {results['error']}"
print("✅ Concurrence gérée correctement (1 succès, 1 échec)")


# ==================================================================
# NETTOYAGE
# ==================================================================
print("\n--- Nettoyage ---")
Ticket.objects.filter(registration__event=event).delete()
for reg in registrations:
    reg.delete()
tt.delete()
event.delete()
for u in users:
    u.delete()
print("✅ Nettoyage OK")


print("\n" + "=" * 60)
print("🎉 TEST DE CONCURRENCE RÉUSSI !")
print("=" * 60)