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

Points de sécurité :
    - Les en-têtes de la réponse DRF (Retry-After sur un 429, WWW-Authenticate
      sur un 401) sont CONSERVÉS : on modifie `response.data`, on ne crée pas
      de nouvelle Response.
    - En production (DEBUG=False), une exception non prévue renvoie un JSON
      générique ; le détail n'est écrit que dans les logs serveur, jamais
      dans la réponse.
"""

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from common.storage.s3 import StorageUnavailableError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Handler personnalisé pour toutes les exceptions DRF.

    Appelé automatiquement par DRF quand une exception est levée dans une vue.
    """
    # 0. Stockage objet indisponible (S3/R2/Supabase…) : 502 propre, sans
    #    jamais exposer les détails internes (bucket, clé, endpoint) au
    #    client. Le détail reste dans les logs.
    if isinstance(exc, StorageUnavailableError):
        view = context.get("view")
        logger.exception(
            "Stockage indisponible | view=%s | exc=%s",
            view.__class__.__name__ if view else "?",
            exc.__class__.__name__,
        )
        return Response(
            {
                "success": False,
                "message": (
                    "Le stockage des fichiers est indisponible pour le moment. "
                    "Réessayez plus tard."
                ),
                "errors": {},
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # 1. Laisser DRF gérer l'exception (il retourne None si non géré)
    response = exception_handler(exc, context)

    if response is None:
        # Exception non prévue (bug, erreur base de données...).
        # En développement : on laisse Django afficher la trace complète.
        if settings.DEBUG:
            return None

        view = context.get("view")
        logger.exception(
            "Unhandled exception | view=%s | exc=%s",
            view.__class__.__name__ if view else "?",
            exc.__class__.__name__,
        )
        return Response(
            {
                "success": False,
                "message": _get_default_message(status.HTTP_500_INTERNAL_SERVER_ERROR),
                "errors": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 2. Reformater la réponse selon notre standard
    status_code = response.status_code
    errors = response.data

    # Message par défaut selon le code HTTP
    message = _get_default_message(status_code)

    # Si DRF a retourné un "detail", on l'utilise comme message principal
    if isinstance(errors, dict) and "detail" in errors:
        message = str(errors.pop("detail"))

    # Si errors n'est pas un dict (ex: liste), on l'enveloppe
    if not isinstance(errors, dict):
        errors = {"non_field_errors": errors}

    # On modifie la réponse existante (au lieu d'en créer une nouvelle)
    # pour conserver ses en-têtes.
    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
    }
    return response


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