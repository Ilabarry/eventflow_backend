"""
Provider Wave (placeholder).

⚠️ NON IMPLÉMENTÉ : l'API officielle Wave n'est pas encore disponible.
Voir : https://wave.com/docs
"""

from apps.payments.providers.base import AbstractPaymentProvider, ProviderResult


class WaveProvider(AbstractPaymentProvider):
    """Provider Wave (placeholder V2)."""

    name = "WAVE"
    is_production_ready = False

    def initiate_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("WaveProvider non implémenté (V2).")

    def get_payment_status(self, payment) -> ProviderResult:
        raise NotImplementedError("WaveProvider non implémenté (V2).")

    def cancel_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("WaveProvider non implémenté (V2).")

    def refund_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("WaveProvider non implémenté (V2).")