"""
Standardisation des réponses API.

Toutes les réponses de l'API EVENTFLOW respectent le format :
    {
        "success": true/false,
        "message": "...",
        "data": {...} ou "errors": {...}
    }

Cela permet au frontend Angular de traiter toutes les réponses
de manière uniforme (via un intercepteur HTTP).
"""

from rest_framework import status
from rest_framework.response import Response


class APIResponse:
    """
    Classe utilitaire pour construire des réponses standardisées.
    """

    @staticmethod
    def success(
        data=None,
        message: str = "Opération réussie.",
        status_code: int = status.HTTP_200_OK,
    ) -> Response:
        """
        Réponse de succès.

        Args:
            data: Les données à retourner (dict, list, None).
            message: Message lisible pour l'utilisateur.
            status_code: Code HTTP (200, 201, 204...).

        Returns:
            Response DRF standardisée.
        """
        payload = {
            "success": True,
            "message": message,
        }
        if data is not None:
            payload["data"] = data
        return Response(payload, status=status_code)

    @staticmethod
    def error(
        message: str = "Une erreur est survenue.",
        errors=None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> Response:
        """
        Réponse d'erreur.

        Args:
            message: Message lisible pour l'utilisateur.
            errors: Dictionnaire d'erreurs détaillées (champ → [messages]).
            status_code: Code HTTP (400, 401, 403, 404, 500...).

        Returns:
            Response DRF standardisée.
        """
        payload = {
            "success": False,
            "message": message,
        }
        if errors is not None:
            payload["errors"] = errors
        return Response(payload, status=status_code)

    @staticmethod
    def created(data=None, message: str = "Ressource créée avec succès.") -> Response:
        """Raccourci pour une réponse 201 Created."""
        return APIResponse.success(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    @staticmethod
    def no_content(message: str = "Opération réussie.") -> Response:
        """Raccourci pour une réponse 204 No Content."""
        return APIResponse.success(
            data=None,
            message=message,
            status_code=status.HTTP_204_NO_CONTENT,
        )