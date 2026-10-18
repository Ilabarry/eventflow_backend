"""
Provider Orange Money (placeholder).

⚠️ NON IMPLÉMENTÉ : l'API officielle Orange Money n'est pas
encore disponible. Ce fichier sert de placeholder pour la V2.

À implémenter quand :
    - Les credentials Orange Money seront obtenus
    - La documentation API sera disponible

Voir : https://developer.orange.com/apis/orange-money-webpay
"""

from apps.payments.providers.base import AbstractPaymentProvider, ProviderResult


class OrangeMoneyProvider(AbstractPaymentProvider):
    """
    Provider Orange Money.

    ⚠️ Toutes les méthodes lèvent NotImplementedError pour l'instant.
    """

    name = "ORANGE_MONEY"
    is_production_ready = False

    def initiate_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("OrangeMoneyProvider non implémenté (V2).")

    def get_payment_status(self, payment) -> ProviderResult:
        raise NotImplementedError("OrangeMoneyProvider non implémenté (V2).")

    def cancel_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("OrangeMoneyProvider non implémenté (V2).")

    def refund_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("OrangeMoneyProvider non implémenté (V2).")