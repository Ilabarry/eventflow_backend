"""
Provider Yas (placeholder).

⚠️ NON IMPLÉMENTÉ : l'API officielle Yas n'est pas encore disponible.
"""

from apps.payments.providers.base import AbstractPaymentProvider, ProviderResult


class YasProvider(AbstractPaymentProvider):
    """Provider Yas (placeholder V2)."""

    name = "YAS"
    is_production_ready = False

    def initiate_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("YasProvider non implémenté (V2).")

    def get_payment_status(self, payment) -> ProviderResult:
        raise NotImplementedError("YasProvider non implémenté (V2).")

    def cancel_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("YasProvider non implémenté (V2).")

    def refund_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("YasProvider non implémenté (V2).")