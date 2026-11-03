#!/usr/bin/env bash
#
# Point d'entrée de production Render.
#
# Le plan gratuit ne propose pas de worker/background service : on lance
# donc le scheduler APScheduler dans le même conteneur que Gunicorn.
# Les tâches sont idempotentes (génération de certificats), un éventuel
# redémarrage ne crée pas de doublons.
set -e

python scheduler.py &
SCHEDULER_PID=$!

# Arrêter proprement le scheduler si Gunicorn s'arrête.
trap 'kill "$SCHEDULER_PID" 2>/dev/null || true' EXIT INT TERM

gunicorn eventflow_backend.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --access-logfile - \
    --error-logfile -
