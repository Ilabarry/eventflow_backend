"""
Provider Card (placeholder).

⚠️ NON IMPLÉMENTÉ : l'intégration carte bancaire se fera via un
prestataire (Stripe, PayDunya, etc.) dont l'API n'est pas encore
choisie.

RAPPEL : ne JAMAIS stocker de numéros de carte, CVV ou données
bancaires sensibles. Utiliser la tokenisation du prestataire.
"""

from apps.payments.providers.base import AbstractPaymentProvider, ProviderResult


class CardProvider(AbstractPaymentProvider):
    """Provider Card (placeholder V2)."""

    name = "CARD"
    is_production_ready = False

    def initiate_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("CardProvider non implémenté (V2).")

    def get_payment_status(self, payment) -> ProviderResult:
        raise NotImplementedError("CardProvider non implémenté (V2).")

    def cancel_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("CardProvider non implémenté (V2).")

    def refund_payment(self, payment) -> ProviderResult:
        raise NotImplementedError("CardProvider non implémenté (V2).")