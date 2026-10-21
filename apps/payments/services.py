"""
Service métier du module Payment.

⚠️ POINTS CRITIQUES :
    1. Le montant est TOUJOURS calculé côté backend (jamais fourni par Angular).
    2. Un seul paiement SUCCESS par Registration (contrainte DB + service).
    3. La création utilise select_for_update() pour éviter les doubles paiements.
    4. L'idempotency_key permet de gérer les retries réseau proprement.
"""

import logging
from django.db import transaction
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.events.constants import ParticipationType
from apps.payments.constants import (
    ACTIVE_STATUSES,
    DEFAULT_CURRENCY,
    REFERENCE_ALPHABET,
    REFERENCE_PREFIX,
    REFERENCE_SUFFIX_LENGTH,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from apps.payments.models import Payment
from apps.payments.providers import get_provider
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.registrations.services import RegistrationService
from common.exceptions.business import (
    InvalidPaymentState,
    PaymentAlreadySuccessful,
    PaymentNotPayable,
    PaymentProviderError,
    PaymentProviderUnavailable,
)

logger = logging.getLogger(__name__)


class PaymentService:
    """Service métier pour les paiements."""

    # ------------------------------------------------------------------
    # GÉNÉRATION DE RÉFÉRENCE
    # ------------------------------------------------------------------
    @staticmethod
    def generate_reference() -> str:
        """Génère une référence unique EVF-PAY-YYYY-XXXXXX."""
        year = timezone.now().year
        suffix = "".join(
            secrets.choice(REFERENCE_ALPHABET)
            for _ in range(REFERENCE_SUFFIX_LENGTH)
        )
        return f"{REFERENCE_PREFIX}-{year}-{suffix}"

    @staticmethod
    def _generate_unique_reference() -> str:
        """Génère une référence unique avec retry."""
        for _ in range(10):
            ref = PaymentService.generate_reference()
            if not Payment.objects.filter(transaction_reference=ref).exists():
                return ref
        raise RuntimeError("Impossible de générer une référence unique.")

    # ------------------------------------------------------------------
    # CALCUL DU MONTANT (SOURCE DE VÉRITÉ)
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_amount(registration: Registration) -> tuple:
        """
        Calcule le montant à payer pour une inscription.

        Règle absolue : le montant vient du backend, jamais d'Angular.

        Returns:
            (amount: Decimal, currency: str)

        Raises:
            PaymentNotPayable: Si l'événement est gratuit.
            ValueError: Si l'événement payant n'a pas de prix.
        """
        event = registration.event

        # Événement gratuit → pas de paiement
        if event.participation_type == ParticipationType.FREE:
            raise PaymentNotPayable(
                detail="Cet événement est gratuit, aucun paiement n'est nécessaire."
            )

        # Événement payant → vérifier que base_price est défini
        if not event.base_price or event.base_price <= 0:
            raise PaymentNotPayable(
                detail="Le prix de cet événement n'est pas défini correctement."
            )

        return event.base_price, DEFAULT_CURRENCY

    # ------------------------------------------------------------------
    # INITIATION D'UN PAIEMENT (CRITIQUE)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def initiate_payment(
        *,
        registration: Registration,
        payment_method: str,
        provider_name: str,
        idempotency_key: str | None = None,
    ) -> Payment:
        """
        Initie un nouveau paiement.

        Étapes :
            1. Vérifier que la Registration est PENDING.
            2. Vérifier qu'aucun paiement SUCCESS n'existe déjà.
            3. Vérifier l'idempotency_key.
            4. Calculer le montant côté backend.
            5. Verrouiller la Registration (select_for_update).
            6. Créer le Payment (PENDING).
            7. Appeler le provider.
            8. Mettre à jour le Payment avec la réponse.

        Raises:
            PaymentNotPayable: Si la Registration n'est pas payable.
            PaymentAlreadySuccessful: Si un paiement SUCCESS existe déjà.
            PaymentProviderUnavailable: Si le provider n'existe pas.
        """
        # 1. Verrouiller la Registration pour éviter les doubles initiations
        locked_registration = Registration.objects.select_for_update().get(
            pk=registration.pk
        )

        # 2. Vérifier le statut de la Registration
        if locked_registration.status != RegistrationStatus.PENDING:
            raise PaymentNotPayable(
                detail=f"L'inscription doit être en attente. Statut actuel : {locked_registration.status}."
            )

        # 3. Vérifier qu'aucun paiement SUCCESS n'existe déjà
        if Payment.objects.filter(
            registration=locked_registration,
            status=PaymentStatus.SUCCESS,
        ).exists():
            raise PaymentAlreadySuccessful()

        # 4. Gérer l'idempotency_key
        if idempotency_key:
            existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                logger.info(
                    "Idempotency key reused | key=%s | payment=%s",
                    idempotency_key, existing.transaction_reference,
                )
                return existing

        # 5. Calculer le montant (côté backend)
        amount, currency = PaymentService.calculate_amount(locked_registration)

        # 6. Créer le Payment
        payment = Payment.objects.create(
            registration=locked_registration,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            provider=provider_name,
            transaction_reference=PaymentService._generate_unique_reference(),
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
        )

        logger.info(
            "Payment initiated | ref=%s | reg=%s | amount=%s %s | provider=%s",
            payment.transaction_reference, locked_registration.reference,
            amount, currency, provider_name,
        )

        # 7. Appeler le provider (dans un try/except pour capturer les erreurs)
        try:
            provider = get_provider(provider_name)
            result = provider.initiate_payment(payment)

            # 8. Mettre à jour le Payment avec la réponse normalisée
            payment.provider_reference = result.provider_reference
            if result.status == PaymentStatus.SUCCESS:
                payment.status = PaymentStatus.SUCCESS
                payment.paid_at = timezone.now()
            elif result.status == PaymentStatus.FAILED:
                payment.status = PaymentStatus.FAILED
                payment.failure_code = result.failure_code
                payment.failure_message = result.message
            # Sinon PENDING par défaut

            payment.metadata = {"provider_message": result.message}
            payment.save()

            # 9. Si SUCCESS → confirmer la Registration ET émettre le ticket
            if payment.status == PaymentStatus.SUCCESS:
                RegistrationService.confirm_registration(
                    registration=locked_registration
                )
                from apps.tickets.services import TicketService
                TicketService.issue_ticket_for_registration(
                    registration=locked_registration
                )

            return payment

        except NotImplementedError as e:
            # Le provider existe mais n'est pas implémenté (placeholders)
            payment.status = PaymentStatus.FAILED
            payment.failure_code = "PROVIDER_NOT_IMPLEMENTED"
            payment.failure_message = str(e)
            payment.save()
            raise PaymentProviderUnavailable(
                detail=f"Le provider '{provider_name}' n'est pas encore disponible."
            )

        except Exception as e:
            logger.exception("Provider error | payment=%s", payment.transaction_reference)
            payment.status = PaymentStatus.FAILED
            payment.failure_code = "PROVIDER_ERROR"
            payment.failure_message = str(e)[:500]
            payment.save()
            raise PaymentProviderError(detail="Erreur du service de paiement.")

    # ------------------------------------------------------------------
    # CONFIRMATION (appelée par simulate ou webhook)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def mark_as_success(*, payment: Payment, provider_reference: str = "") -> Payment:
        """
        Marque un paiement comme SUCCESS et confirme la Registration.

        Utilisé par :
            - Le simulateur (DevelopmentPaymentProvider)
            - Les futurs webhooks
        """
        if payment.status == PaymentStatus.SUCCESS:
            return payment  # idempotent

        if not payment.can_transition_to(PaymentStatus.SUCCESS):
            raise InvalidPaymentState(
                detail=f"Transition '{payment.status}' → 'SUCCESS' non autorisée."
            )

        payment.status = PaymentStatus.SUCCESS
        payment.paid_at = timezone.now()
        if provider_reference:
            payment.provider_reference = provider_reference
        payment.save()

        # Confirmer la Registration
        RegistrationService.confirm_registration(
            registration=payment.registration
        )

                # Confirmer la Registration
        RegistrationService.confirm_registration(
            registration=payment.registration
        )

        # ✅ Émettre le ticket (idempotent)
        try:
            from apps.tickets.services import TicketService
            TicketService.issue_ticket_for_registration(
                registration=payment.registration
            )
        except Exception as e:
            logger.exception(
                "Ticket issuance failed after payment SUCCESS | payment=%s | reg=%s",
                payment.transaction_reference,
                payment.registration.reference,
            )

        logger.info(
            "Payment marked as SUCCESS | ref=%s | reg=%s",
            payment.transaction_reference, payment.registration.reference,
        )

        # ⚠️ NOUVEAU : notifier le participant
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=payment.registration.participant,
                    title="Paiement réussi",
                    message=(
                        f"Votre paiement de {payment.amount} {payment.currency} "
                        f"pour « {payment.registration.event.title} » est confirmé."
                    ),
                    notification_type=NotificationType.PAYMENT,
                    related_entity_type="payment",
                    related_entity_id=str(payment.id),
                    metadata={"url": f"/participant/paiements/{payment.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on payment success | err=%s", e)

        # ⚠️ NOUVEAU : notifier l'organisateur
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=payment.registration.event.organizer,
                    title="Paiement reçu",
                    message=(
                        f"Un paiement de {payment.amount} {payment.currency} a été reçu "
                        f"pour « {payment.registration.event.title} »."
                    ),
                    notification_type=NotificationType.PAYMENT,
                    related_entity_type="payment",
                    related_entity_id=str(payment.id),
                    metadata={"url": f"/organizer/paiements/{payment.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on payment success (organizer) | err=%s", e)

        return payment

    # ------------------------------------------------------------------
    # ÉCHEC
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def mark_as_failed(
        *,
        payment: Payment,
        failure_code: str = "",
        failure_message: str = "",
    ) -> Payment:
        """Marque un paiement comme FAILED."""
        if payment.status == PaymentStatus.FAILED:
            return payment

        if not payment.can_transition_to(PaymentStatus.FAILED):
            raise InvalidPaymentState(
                detail=f"Transition '{payment.status}' → 'FAILED' non autorisée."
            )

        payment.status = PaymentStatus.FAILED
        payment.failure_code = failure_code
        payment.failure_message = failure_message
        payment.save()

        logger.info("Payment marked as FAILED | ref=%s", payment.transaction_reference)

        # ⚠️ NOUVEAU : notifier le participant
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=payment.registration.participant,
                    title="Paiement échoué",
                    message=(
                        f"Votre paiement pour « {payment.registration.event.title} » "
                        f"a échoué. Vous pouvez réessayer."
                    ),
                    notification_type=NotificationType.PAYMENT,
                    related_entity_type="payment",
                    related_entity_id=str(payment.id),
                    metadata={"url": f"/participant/paiements/{payment.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on payment failure | err=%s", e)

        return payment

    # ------------------------------------------------------------------
    # ANNULATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def cancel_payment(*, payment: Payment) -> Payment:
        """Annule un paiement PENDING."""
        if payment.status == PaymentStatus.CANCELLED:
            raise InvalidPaymentState(detail="Ce paiement est déjà annulé.")

        if not payment.can_be_cancelled():
            raise InvalidPaymentState(
                detail=f"Seul un paiement PENDING peut être annulé. Statut : {payment.status}."
            )

        payment.status = PaymentStatus.CANCELLED
        payment.cancelled_at = timezone.now()
        payment.save()

        logger.info("Payment cancelled | ref=%s", payment.transaction_reference)
        return payment

    # ------------------------------------------------------------------
    # REMBOURSEMENT
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def refund_payment(*, payment: Payment) -> Payment:
        """Rembourse un paiement SUCCESS."""
        if payment.status == PaymentStatus.REFUNDED:
            raise InvalidPaymentState(detail="Ce paiement est déjà remboursé.")

        if not payment.can_be_refunded():
            raise InvalidPaymentState(
                detail=f"Seul un paiement SUCCESS peut être remboursé. Statut : {payment.status}."
            )

        # Appeler le provider pour le remboursement
        try:
            provider = get_provider(payment.provider)
            result = provider.refund_payment(payment)
        except NotImplementedError:
            raise PaymentProviderUnavailable(
                detail=f"Le remboursement n'est pas disponible pour le provider '{payment.provider}'."
            )

        if result.status != "REFUNDED":
            raise PaymentProviderError(detail="Le remboursement a échoué côté provider.")

        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = timezone.now()
        payment.save()

        logger.info("Payment refunded | ref=%s", payment.transaction_reference)
        return payment

    # ------------------------------------------------------------------
    # SIMULATION (développement uniquement)
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def simulate_payment_result(*, payment: Payment, result: str) -> Payment:
        """
        Simule un résultat de paiement (DEBUG uniquement).

        Args:
            payment: Le paiement à simuler.
            result: "SUCCESS", "FAILED", "CANCELLED" ou "PENDING".
        """
        if not settings.PAYMENT_DEVELOPMENT_ENABLED:
            raise PaymentProviderUnavailable(
                detail="La simulation n'est pas disponible en production."
            )

        if payment.provider != PaymentProvider.DEVELOPMENT:
            raise InvalidPaymentState(
                detail="Seuls les paiements de développement peuvent être simulés."
            )

        from apps.payments.providers.development import DevelopmentPaymentProvider

        provider_result = DevelopmentPaymentProvider.simulate_result(payment, result)

        if provider_result.status == "SUCCESS":
            return PaymentService.mark_as_success(
                payment=payment,
                provider_reference=provider_result.provider_reference,
            )
        elif provider_result.status == "FAILED":
            return PaymentService.mark_as_failed(
                payment=payment,
                failure_code=provider_result.failure_code,
                failure_message=provider_result.message,
            )
        elif provider_result.status == "CANCELLED":
            payment.status = PaymentStatus.CANCELLED
            payment.cancelled_at = timezone.now()
            payment.save()
            return payment

        # PENDING : rien à faire
        return payment