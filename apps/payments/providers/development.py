"""
Provider de développement : permet de tester le cycle complet
de paiement sans dépendre d'un provider externe.

⚠️ ATTENTION : ce provider ne fait AUCUN vrai paiement. Il simule
les réponses des vrais providers. Ne doit JAMAIS être utilisé en
production (voir PAYMENT_DEVELOPMENT_ENABLED).
"""

import logging
import uuid

from django.conf import settings
from django.utils import timezone

from apps.payments.providers.base import AbstractPaymentProvider, ProviderResult

logger = logging.getLogger(__name__)


class DevelopmentPaymentProvider(AbstractPaymentProvider):
    """
    Provider de développement.

    Comportement par défaut : retourne PENDING avec une référence fictive.
    Le statut final (SUCCESS/FAILED/CANCELLED) est simulé via l'API
    /api/payments/development/{id}/simulate/.

    En mode `auto_confirm`, il retourne directement SUCCESS.
    """

    name = "DEVELOPMENT"
    is_production_ready = False

    # Configuration : si True, retourne directement SUCCESS à l'initiation
    # Utile pour tester rapidement (Angular peut payer en 1 clic).
    auto_confirm = False

    # ------------------------------------------------------------------
    # INITIATION
    # ------------------------------------------------------------------
    def initiate_payment(self, payment) -> ProviderResult:
        """
        Initie un paiement simulé.

        Retourne :
            - PENDING si auto_confirm=False (défaut)
            - SUCCESS si auto_confirm=True
        """
        if not settings.PAYMENT_DEVELOPMENT_ENABLED:
            logger.error(
                "DevelopmentPaymentProvider used while disabled | payment=%s",
                payment.transaction_reference,
            )
            return ProviderResult(
                status="FAILED",
                message="Le provider de développement est désactivé.",
                failure_code="PROVIDER_DISABLED",
            )

        # Génère une référence fictive pour simuler un vrai provider
        provider_ref = f"DEV-{uuid.uuid4().hex[:12].upper()}"

        logger.info(
            "DevelopmentProvider.initiate | payment=%s | auto_confirm=%s",
            payment.transaction_reference, self.auto_confirm,
        )

        if self.auto_confirm:
            return ProviderResult(
                status="SUCCESS",
                provider_reference=provider_ref,
                message="Paiement simulé réussi automatiquement.",
                raw_response={"simulated": True, "auto": True},
            )

        return ProviderResult(
            status="PENDING",
            provider_reference=provider_ref,
            payment_url=f"https://dev.eventflow.sn/pay/{provider_ref}",
            message="Paiement en attente de confirmation (simulation).",
            raw_response={"simulated": True, "auto": False},
        )

    # ------------------------------------------------------------------
    # STATUT
    # ------------------------------------------------------------------
    def get_payment_status(self, payment) -> ProviderResult:
        """
        Retourne le statut actuel du paiement.

        En dev, on retourne simplement le statut actuel du Payment
        (car il n'y a pas de "vrai" provider externe à interroger).
        """
        return ProviderResult(
            status=payment.status,
            provider_reference=payment.provider_reference,
            message="Statut simulé (dev).",
            raw_response={"simulated": True},
        )

    # ------------------------------------------------------------------
    # ANNULATION
    # ------------------------------------------------------------------
    def cancel_payment(self, payment) -> ProviderResult:
        """Simule une annulation."""
        logger.info(
            "DevelopmentProvider.cancel | payment=%s",
            payment.transaction_reference,
        )
        return ProviderResult(
            status="CANCELLED",
            provider_reference=payment.provider_reference,
            message="Paiement simulé annulé.",
            raw_response={"simulated": True},
        )

    # ------------------------------------------------------------------
    # REMBOURSEMENT
    # ------------------------------------------------------------------
    def refund_payment(self, payment) -> ProviderResult:
        """Simule un remboursement."""
        logger.info(
            "DevelopmentProvider.refund | payment=%s",
            payment.transaction_reference,
        )
        return ProviderResult(
            status="REFUNDED",
            provider_reference=payment.provider_reference,
            message="Paiement simulé remboursé.",
            raw_response={"simulated": True},
        )

    # ------------------------------------------------------------------
    # SIMULATION (spécifique au provider dev)
    # ------------------------------------------------------------------
    @staticmethod
    def simulate_result(payment, result: str) -> ProviderResult:
        """
        Simule un résultat de paiement (SUCCESS, FAILED, CANCELLED, PENDING).

        Utilisé UNIQUEMENT par l'endpoint /simulate/ en développement.

        Args:
            payment: Instance Payment.
            result: "SUCCESS", "FAILED", "CANCELLED" ou "PENDING".

        Returns:
            ProviderResult avec le statut demandé.
        """
        result = result.upper()

        if result == "SUCCESS":
            return ProviderResult(
                status="SUCCESS",
                provider_reference=payment.provider_reference or f"DEV-{uuid.uuid4().hex[:12].upper()}",
                message="Paiement simulé réussi.",
                raw_response={"simulated": True, "result": "SUCCESS"},
            )

        if result == "FAILED":
            return ProviderResult(
                status="FAILED",
                provider_reference=payment.provider_reference or f"DEV-{uuid.uuid4().hex[:12].upper()}",
                message="Paiement simulé échoué.",
                failure_code="SIMULATED_FAILURE",
                raw_response={"simulated": True, "result": "FAILED"},
            )

        if result == "CANCELLED":
            return ProviderResult(
                status="CANCELLED",
                provider_reference=payment.provider_reference or f"DEV-{uuid.uuid4().hex[:12].upper()}",
                message="Paiement simulé annulé.",
                raw_response={"simulated": True, "result": "CANCELLED"},
            )

        # Par défaut : PENDING
        return ProviderResult(
            status="PENDING",
            provider_reference=payment.provider_reference or f"DEV-{uuid.uuid4().hex[:12].upper()}",
            message="Paiement simulé en attente.",
            raw_response={"simulated": True, "result": "PENDING"},
        )