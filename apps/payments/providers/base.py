"""
Interface abstraite des providers de paiement.

Tout provider doit hériter de AbstractPaymentProvider et implémenter
les 4 méthodes. Le reste du code utilise UNIQUEMENT cette interface,
ce qui permet d'ajouter de nouveaux providers sans toucher au reste
de l'application.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# ==================================================================
# RÉSULTAT NORMALISÉ D'UN APPEL PROVIDER
# ==================================================================
@dataclass
class ProviderResult:
    """
    Résultat normalisé d'un appel provider.

    Tous les providers doivent retourner une instance de cette classe,
    quelle que soit la réponse réelle de l'API externe.

    Attributs :
        status: Statut normalisé ("PENDING", "SUCCESS", "FAILED", "CANCELLED")
        provider_reference: Référence externe du provider (peut être vide)
        payment_url: URL de paiement à ouvrir (peut être None)
        message: Message lisible pour l'utilisateur
        failure_code: Code technique d'échec (peut être vide)
        raw_response: Réponse brute du provider (pour debug)
    """
    status: str
    provider_reference: str = ""
    payment_url: Optional[str] = None
    message: str = ""
    failure_code: str = ""
    raw_response: Optional[dict] = None


# ==================================================================
# INTERFACE ABSTRAITE
# ==================================================================
class AbstractPaymentProvider(ABC):
    """
    Interface abstraite pour tous les providers de paiement.

    ⚠️ IMPORTANT : ne jamais exposer cette classe directement
    au reste du code. Toujours passer par la factory get_provider().
    """

    # Nom unique du provider (doit correspondre à PaymentProvider enum)
    name: str = ""

    # Indique si le provider est prêt pour la production
    is_production_ready: bool = False

    @abstractmethod
    def initiate_payment(self, payment) -> ProviderResult:
        """
        Initie un paiement.

        Args:
            payment: Instance Payment (avec amount, currency, etc.).

        Returns:
            ProviderResult avec le statut initial.
        """
        ...

    @abstractmethod
    def get_payment_status(self, payment) -> ProviderResult:
        """
        Récupère le statut actuel d'un paiement.

        Utile pour :
            - Le polling Angular
            - La réconciliation asynchrone
        """
        ...

    @abstractmethod
    def cancel_payment(self, payment) -> ProviderResult:
        """
        Annule un paiement.

        Possible uniquement si le paiement est encore PENDING.
        """
        ...

    @abstractmethod
    def refund_payment(self, payment) -> ProviderResult:
        """
        Rembourse un paiement.

        Possible uniquement si le paiement est SUCCESS.
        """
        ...