"""
Génère les certificats pour les inscriptions éligibles.

Éligibilité :
    - Registration CONFIRMED
    - Attendance PRESENT
    - Event terminé (end_at < now)
    - Pas de certificat actif (PENDING ou ISSUED)

Usage :
    python manage.py generate_certificates
    python manage.py generate_certificates --event <uuid>
    python manage.py generate_certificates --dry-run
    python manage.py generate_certificates --since 7   # derniers 7 jours
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.attendance.constants import AttendanceStatus
from apps.certificates.constants import CertificateStatus
from apps.certificates.models import Certificate
from apps.certificates.services import CertificateService
from apps.events.constants import EventStatus
from apps.events.models import Event
from apps.registrations.constants import RegistrationStatus


class Command(BaseCommand):
    help = "Génère les certificats pour les inscriptions éligibles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event",
            type=str,
            help="UUID d'un événement spécifique (sinon : tous les événements terminés).",
        )
        parser.add_argument(
            "--since",
            type=int,
            default=None,
            help="Limiter aux événements terminés depuis N jours (par défaut : tous).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simuler sans créer de certificats.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options["dry_run"]
        since_days = options["since"]
        event_id = options["event"]

        # 1. Construire le queryset des événements
        events_qs = Event.objects.filter(
            status=EventStatus.PUBLISHED,
            end_at__lt=now,
        ).exclude(status=EventStatus.CANCELLED)

        if event_id:
            events_qs = events_qs.filter(id=event_id)
        if since_days:
            events_qs = events_qs.filter(end_at__gte=now - timedelta(days=since_days))

        events = list(events_qs.select_related("organizer"))
        if not events:
            self.stdout.write(self.style.WARNING("Aucun événement terminé à traiter."))
            return

        self.stdout.write(f"→ {len(events)} événement(s) à traiter.\n")

        total_generated = 0
        total_skipped = 0
        total_errors = 0

        for event in events:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n📅 {event.title}"))

            # 2. Trouver les inscriptions éligibles
            eligible = (
                event.registrations
                .filter(
                    status=RegistrationStatus.CONFIRMED,
                    attendance__status=AttendanceStatus.PRESENT,
                )
                .exclude(certificate__isnull=False)  # pas de certificat existant
                .select_related("participant", "attendance")
            )

            count = eligible.count()
            if count == 0:
                self.stdout.write("  (aucune inscription éligible)")
                continue

            self.stdout.write(f"  {count} inscription(s) éligible(s)")

            for registration in eligible:
                name = registration.participant.full_name
                ref = registration.reference

                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f"  [DRY-RUN] {name} ({ref})")
                    )
                    total_generated += 1
                    continue

                try:
                    with transaction.atomic():
                        cert = CertificateService.generate_certificate(registration)
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ {name} ({ref}) → {cert.reference}")
                    )
                    total_generated += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ {name} ({ref}) : {e}")
                    )
                    total_errors += 1

        # 3. Bilan
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ {total_generated} certificat(s) généré(s)"
            )
        )
        if total_skipped:
            self.stdout.write(f"⏭  {total_skipped} ignoré(s)")
        if total_errors:
            self.stdout.write(
                self.style.ERROR(f"✗ {total_errors} erreur(s)")
            )
        if dry_run:
            self.stdout.write(self.style.WARNING("(DRY-RUN — rien n'a été enregistré)"))