"""Pagination spécifique au module Payment."""

from common.pagination.standard import StandardPagination


class PaymentPagination(StandardPagination):
    """Pagination pour les listes de paiements."""
    page_size = 20
    max_page_size = 100