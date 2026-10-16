"""
Pagination spécifique au module Event.

Pour l'instant, on hérite de StandardPagination sans modification.
Cette classe existe pour permettre des ajustements futurs
(taille de page différente pour les événements, par exemple).
"""

from common.pagination.standard import StandardPagination


class EventPagination(StandardPagination):
    """
    Pagination pour les listes d'événements.

    Par défaut : 12 événements par page (adapté aux grilles Angular).
    Maximum : 50.
    """
    page_size = 12
    max_page_size = 50