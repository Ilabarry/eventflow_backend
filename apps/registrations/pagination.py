"""
Pagination spécifique au module Registration.
"""

from common.pagination.standard import StandardPagination


class RegistrationPagination(StandardPagination):
    """Pagination pour les listes d'inscriptions."""
    page_size = 20
    max_page_size = 100