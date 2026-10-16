"""
Pagination standardisée pour EVENTFLOW.

Toutes les listes paginées de l'API utilisent cette classe pour
garantir un format uniforme et limiter les abus (page_size max).

Format de réponse :
    {
        "count": 42,
        "next": "http://.../api/events/?page=2",
        "previous": null,
        "results": [...]
    }

Le frontend Angular peut facilement exploiter cette structure.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """
    Pagination par numéro de page.

    Paramètres URL :
        ?page=1             → numéro de page (défaut : 1)
        ?page_size=12       → taille de page (défaut : 12, max : 50)

    Le `page_size` est limité à 50 pour éviter les abus
    (un client ne peut pas demander 100 000 résultats).
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50

    def get_paginated_response(self, data):
        """
        Personnalise la réponse pour inclure les métadonnées utiles
        au frontend (total_pages, current_page, etc.).
        """
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )