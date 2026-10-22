"""
Script pour créer 5 inscriptions de test sur un événement gratuit PUBLISHED.
Usage : python seed_inscriptions.py
"""

import os
import django

# ✅ Initialisation Django AVANT les imports des models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventflow_backend.settings')
django.setup()

from apps.events.models import Event
from apps.accounts.models import User, Role
from apps.registrations.services import RegistrationService


def main():
    # 1. Récupérer un événement PUBLISHED gratuit
    event = Event.objects.filter(
        organizer__email='organisateur@gmail.com',
        status='PUBLISHED',
        participation_type='FREE',
    ).first()

    if not event:
        print("❌ Aucun événement PUBLISHED gratuit.")
        return

    print(f"Événement ciblé : {event.title}")

    # 2. Récupérer le rôle participant
    role = Role.objects.filter(name='participant').first()
    if not role:
        print("❌ Rôle 'participant' introuvable.")
        return

    # 3. Créer 5 participants + inscriptions
    created_count = 0
    for i in range(5):
        email = f'test-participant-{i}@eventflow.sn'
        phone = f'+22177000000{i}'  # téléphone UNIQUE obligatoire

        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': 'Test',
                'last_name': f'Participant {i+1}',
                'phone': phone,
                'is_active': True,
            },
        )

        if user_created:
            user.set_password('TestPass123!')
            user.save()
            user.roles.add(role)
            print(f"  👤 User créé : {email}")
        else:
            print(f"  ♻️  User existant : {email}")

        # 4. Créer une inscription
        try:
            reg = RegistrationService.create_registration(
                participant=user,
                event=event,
                ticket_type=None,
            )
            created_count += 1
            print(f"  ✅ Inscription {reg.reference} — {user.email}")
        except Exception as e:
            print(f"  ⚠️  {user.email} : {e}")

    print(f"\n✅ {event.registrations.count()} inscriptions sur « {event.title} »")


if __name__ == '__main__':
    main()