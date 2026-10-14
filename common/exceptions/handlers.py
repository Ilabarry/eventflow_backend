"""
Handler d'exceptions personnalisé pour DRF.

Par défaut, DRF retourne des erreurs au format brut :
    {"email": ["Ce champ est obligatoire."]}

Ce handler les enveloppe dans notre format standard :
    {
        "success": false,
        "message": "Erreur de validation.",
        "errors": {"email": ["Ce champ est obligatoire."]}
    }
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Handler personnalisé pour toutes les exceptions DRF.

    Appelé automatiquement par DRF quand une exception est levée
    dans une vue. On délègue d'abord au handler DRF par défaut,
    puis on reformate la réponse.
    """
    # 1. Laisser DRF gérer l'exception (il retourne None si non géré)
    response = exception_handler(exc, context)

    if response is None:
        # Exception non gérée par DRF : laisser Django gérer (500)
        return None

    # 2. Reformater la réponse selon notre standard
    status_code = response.status_code
    errors = response.data

    # Message par défaut selon le code HTTP
    message = _get_default_message(status_code)

    # Si DRF a retourné un "detail", on l'utilise comme message principal
    if isinstance(errors, dict) and "detail" in errors:
        message = str(errors.pop("detail"))

    # Si errors est une liste simple (ex: PermissionDenied), on la garde
    if not isinstance(errors, dict):
        errors = {"non_field_errors": errors}

    return Response(
        {
            "success": False,
            "message": message,
            "errors": errors,
        },
        status=status_code,
    )


def _get_default_message(status_code: int) -> str:
    """Retourne un message par défaut selon le code HTTP."""
    messages = {
        status.HTTP_400_BAD_REQUEST: "Données invalides.",
        status.HTTP_401_UNAUTHORIZED: "Authentification requise.",
        status.HTTP_403_FORBIDDEN: "Accès refusé.",
        status.HTTP_404_NOT_FOUND: "Ressource introuvable.",
        status.HTTP_405_METHOD_NOT_ALLOWED: "Méthode non autorisée.",
        status.HTTP_409_CONFLICT: "Conflit avec une ressource existante.",
        status.HTTP_429_TOO_MANY_REQUESTS: "Trop de requêtes. Réessayez plus tard.",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Erreur interne du serveur.",
    }
    return messages.get(status_code, "Une erreur est survenue.")