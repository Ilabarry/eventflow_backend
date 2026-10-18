"""Pagination du module Tickets."""

from common.pagination.standard import StandardPagination


class TicketPagination(StandardPagination):
    page_size = 20
    max_page_size = 100


class TicketTypePagination(StandardPagination):
    page_size = 10
    max_page_size = 50