"""
Endpoint de santé de l'API EVENTFLOW.

Utilisé par Render (healthCheckPath) et par les sondes de disponibilité.
Il doit rester :
    - public (aucune authentification) ;
    - très léger (aucune requête métier) ;
    - fiable : on vérifie simplement que la base répond.
"""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "HEAD"])  # HEAD accepté pour les sondes (Render, LB)
def health_check(request):
    """Retourne 200 si l'application et la base sont disponibles, 503 sinon."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {"status": "error", "database": "unavailable"},
            status=503,
        )

    return JsonResponse(
        {"status": "ok", "database": "ok"},
        status=200,
    )
