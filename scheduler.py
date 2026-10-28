"""
Scheduler APScheduler pour EVENTFLOW.

Lance en arrière-plan les tâches périodiques :
    - Génération des certificats pour les événements terminés

Usage :
    python scheduler.py

⚠️ En production, préférez un vrai démon (systemd, supervisord).
    Sous Windows, ce script suffit pour le développement.
"""
import logging
import os
import sys
from pathlib import Path

# Ajoute le dossier du projet au PYTHONPATH pour que Django soit importable
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Doit être défini AVANT l'import de django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventflow_backend.settings")

import django  # noqa: E402
django.setup()

from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("eventflow.scheduler")


# ------------------------------------------------------------------
# Tâches
# ------------------------------------------------------------------
def generate_certificates_job() -> None:
    """Génère les certificats pour les inscriptions éligibles."""
    logger.info("=== Génération des certificats ===")
    try:
        call_command("generate_certificates")
        logger.info("✓ Génération terminée")
    except Exception:
        logger.exception("✗ Échec de la génération des certificats")


# ------------------------------------------------------------------
# Point d'entrée
# ------------------------------------------------------------------
def main() -> None:
    scheduler = BlockingScheduler(timezone="Africa/Dakar")

    # Génération des certificats : tous les jours à 3h du matin
    scheduler.add_job(
        generate_certificates_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="generate_certificates",
        name="Génération quotidienne des certificats",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler démarré.")
    logger.info("  → Certificats : tous les jours à 3h00 (Africa/Dakar)")
    logger.info("  Ctrl+C pour arrêter.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté proprement.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()