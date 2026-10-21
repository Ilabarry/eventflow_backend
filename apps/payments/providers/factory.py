"""
Factory pour récupérer le bon provider selon le nom demandé.

C'est le SEUL point d'entrée pour obtenir un provider.
Le reste du code n'importe jamais directement un provider concret.
"""

from apps.payments.constants import PaymentProvider
from apps.payments.providers.base import AbstractPaymentProvider
from apps.payments.providers.card import CardProvider
from apps.payments.providers.development import DevelopmentPaymentProvider
from apps.payments.providers.orange_money import OrangeMoneyProvider
from apps.payments.providers.wave import WaveProvider
from apps.payments.providers.yas import YasProvider
from common.exceptions.business import PaymentProviderUnavailable


# Registre : nom du provider → classe
_PROVIDERS = {
    PaymentProvider.DEVELOPMENT: DevelopmentPaymentProvider,
    PaymentProvider.ORANGE_MONEY: OrangeMoneyProvider,
    PaymentProvider.WAVE: WaveProvider,
    PaymentProvider.YAS: YasProvider,
    PaymentProvider.CARD: CardProvider,
}


def get_provider(provider_name: str) -> AbstractPaymentProvider:
    """
    Retourne une instance du provider demandé.

    Args:
        provider_name: Le nom du provider (valeur de PaymentProvider).

    Returns:
        Une instance de AbstractPaymentProvider.

    Raises:
        PaymentProviderUnavailable: Si le provider n'existe pas.
    """
    provider_class = _PROVIDERS.get(provider_name)

    if provider_class is None:
        raise PaymentProviderUnavailable(
            detail=f"Provider inconnu : '{provider_name}'."
        )

    return provider_class()