import os
import django
import random
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventflow_backend.settings")
django.setup()

from django.utils import timezone
from apps.accounts.models import User
from apps.events.models import Event
from apps.registrations.models import Registration
from apps.registrations.constants import RegistrationStatus

def main():
    print("🚀 Ajout d'inscriptions aux événements existants\n")

    now = timezone.now()

    # Récupérer les événements déjà créés (ceux du seed précédent)
    titles = [
        "Atelier Bureautique", "Conférence Tech", "Meetup Design",
        "Formation Marketing", "Séminaire Leadership", "Workshop IA"
    ]
    events = list(Event.objects.filter(title__in=titles))
    
    if not events:
        print("❌ Aucun événement de test trouvé. Lancez d'abord la Solution 1.")
        return

    print(f"✅ {len(events)} événements existants trouvés.\n")

    # Récupérer les participants
    participant_emails = [f"participant{i}@gmail.com" for i in range(2, 23)]
    participants = list(User.objects.filter(email__in=participant_emails))
    print(f"✅ {len(participants)} participants trouvés.\n")

    total = 0
    skipped = 0

    print("📝 Ajout d'inscriptions...")
    for p in participants:
        # Chaque participant s'inscrit à 1 à 3 événements
        n = random.randint(1, 3)
        picked = random.sample(events, n)

        for event in picked:
            # Vérifier si le participant n'est pas déjà inscrit
            if Registration.objects.filter(participant=p, event=event).exists():
                skipped += 1
                continue

            # Date d'inscription : répartie dans le passé de l'événement
            # On utilise la date de début de l'event - X jours
            event_start = event.start_at
            days_before = random.randint(1, 30)
            reg_date = event_start - timedelta(days=days_before)

            # Statut
            status = (
                RegistrationStatus.CONFIRMED
                if event.participation_type == "FREE"
                else RegistrationStatus.PENDING
            )

            # Création
            reg = Registration.objects.create(
                participant=p,
                event=event,
                reference=f"EVF-REG-{now.year}-{random.randint(10000, 99999)}",
                status=status,
            )
            
            # Forcer la date d'inscription (registered_at est auto_now_add)
            Registration.objects.filter(pk=reg.pk).update(registered_at=reg_date)
            total += 1

    print(f"\n🎉 Terminé !")
    print(f"   • {total} nouvelles inscriptions créées")
    print(f"   • {skipped} inscriptions déjà existantes (ignorées)")

if __name__ == "__main__":
    main()