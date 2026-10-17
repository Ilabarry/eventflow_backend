"""
Vues API du module Payment.

Toutes les réponses utilisent APIResponse.
La logique métier est dans PaymentService.
Ces vues restent fines.
"""

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.events.models import Event
from apps.payments.filters import PaymentFilter
from apps.payments.models import Payment
from apps.payments.pagination import PaymentPagination
from apps.payments.permissions import (
    IsAdminOnly,
    IsPaymentOwner,
    IsPaymentOwnerOrEventOrganizer,
)
from apps.payments.selectors import (
    get_event_payment_stats,
    get_event_payments,
    get_payment_by_id,
    get_payments_for_user,
    get_registration_payments,
)
from apps.payments.serializers import (
    InitiatePaymentSerializer,
    PaymentDetailSerializer,
    PaymentOrganizerSerializer,
    PaymentSerializer,
    PaymentStatsSerializer,
    SimulatePaymentSerializer,
)
from apps.payments.services import PaymentService
from apps.registrations.models import Registration
from common.responses.standard import APIResponse


# ==================================================================
# INITIATION
# ==================================================================
class InitiatePaymentView(APIView):
    """
    POST /api/payments/initiate/

    Initie un paiement pour une inscription PENDING.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        registration = serializer.registration

        # Vérifier que l'utilisateur est bien le participant
        if registration.participant_id != request.user.id:
            return APIResponse.error(
                message="Vous n'êtes pas autorisé à payer cette inscription.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Récupérer l'idempotency_key depuis le header (optionnel)
        idempotency_key = request.headers.get("Idempotency-Key", "") or None

        payment = PaymentService.initiate_payment(
            registration=registration,
            payment_method=serializer.validated_data["payment_method"],
            provider_name=serializer.validated_data["provider"],
            idempotency_key=idempotency_key,
        )

        return APIResponse.created(
            data=PaymentDetailSerializer(payment, context={"request": request}).data,
            message="Paiement initié.",
        )


# ==================================================================
# MES PAIEMENTS
# ==================================================================
class MyPaymentsView(APIView):
    """GET /api/payments/me/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_payments_for_user(request.user)

        filterset = PaymentFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = PaymentPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = PaymentSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message="Paiements récupérés.",
        )


# ==================================================================
# DÉTAIL
# ==================================================================
class PaymentDetailView(APIView):
    """GET /api/payments/{id}/"""

    permission_classes = [IsAuthenticated, IsPaymentOwnerOrEventOrganizer]

    def get(self, request, pk):
        payment = get_payment_by_id(pk)
        if not payment:
            return APIResponse.error(
                message="Paiement introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, payment)

        # Choisir le bon serializer selon le contexte
        is_organizer = payment.registration.event.organizer_id == request.user.id
        is_admin = request.user.is_superuser or request.user.is_staff

        if is_organizer or (is_admin and payment.registration.participant_id != request.user.id):
            serializer = PaymentOrganizerSerializer(payment, context={"request": request})
        else:
            serializer = PaymentDetailSerializer(payment, context={"request": request})

        return APIResponse.success(
            data=serializer.data,
            message="Paiement récupéré.",
        )


# ==================================================================
# STATUT (POLLING)
# ==================================================================
class PaymentStatusView(APIView):
    """GET /api/payments/{id}/status/"""

    permission_classes = [IsAuthenticated, IsPaymentOwnerOrEventOrganizer]

    def get(self, request, pk):
        payment = get_payment_by_id(pk)
        if not payment:
            return APIResponse.error(
                message="Paiement introuvable.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, payment)

        return APIResponse.success(
            data={
                "id": str(payment.id),
                "status": payment.status,
                "paid_at": payment.paid_at,
            },
            message="Statut du paiement.",
        )


# ==================================================================
# ANNULATION
# ==================================================================
class PaymentCancelView(APIView):
    """POST /api/payments/{id}/cancel/"""

    permission_classes = [IsAuthenticated, IsPaymentOwner]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        self.check_object_permissions(request, payment)

        payment = PaymentService.cancel_payment(payment=payment)

        return APIResponse.success(
            data=PaymentDetailSerializer(payment, context={"request": request}).data,
            message="Paiement annulé.",
        )


# ==================================================================
# REMBOURSEMENT (ADMIN)
# ==================================================================
class PaymentRefundView(APIView):
    """POST /api/payments/{id}/refund/"""

    permission_classes = [IsAuthenticated, IsAdminOnly]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)

        payment = PaymentService.refund_payment(payment=payment)

        return APIResponse.success(
            data=PaymentDetailSerializer(payment, context={"request": request}).data,
            message="Paiement remboursé.",
        )


# ==================================================================
# PAIEMENTS D'UNE INSCRIPTION
# ==================================================================
class RegistrationPaymentsView(APIView):
    """GET /api/registrations/{registration_id}/payments/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, registration_id):
        registration = get_object_or_404(Registration, pk=registration_id)

        is_admin = request.user.is_superuser or request.user.is_staff
        is_participant = registration.participant_id == request.user.id
        is_organizer = registration.event.organizer_id == request.user.id

        if not (is_admin or is_participant or is_organizer):
            return APIResponse.error(
                message="Vous n'êtes pas autorisé à voir ces paiements.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        queryset = get_registration_payments(registration)
        serializer = PaymentDetailSerializer(queryset, many=True, context={"request": request})

        return APIResponse.success(
            data=serializer.data,
            message=f"Paiements de l'inscription {registration.reference}.",
        )


# ==================================================================
# PAIEMENTS D'UN ÉVÉNEMENT (ORGANISATEUR)
# ==================================================================
class EventPaymentsView(APIView):
    """GET /api/events/{event_id}/payments/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        is_admin = request.user.is_superuser or request.user.is_staff
        is_owner = event.organizer_id == request.user.id
        if not (is_admin or is_owner):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        queryset = get_event_payments(event)
        filterset = PaymentFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return APIResponse.error(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paginator = PaymentPagination()
        page = paginator.paginate_queryset(filterset.qs, request, view=self)
        serializer = PaymentOrganizerSerializer(page, many=True, context={"request": request})

        return APIResponse.success(
            data=paginator.get_paginated_response(serializer.data).data,
            message=f"Paiements de '{event.title}'.",
        )


# ==================================================================
# STATISTIQUES D'UN ÉVÉNEMENT
# ==================================================================
class EventPaymentStatsView(APIView):
    """GET /api/events/{event_id}/payments/stats/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        is_admin = request.user.is_superuser or request.user.is_staff
        is_owner = event.organizer_id == request.user.id
        if not (is_admin or is_owner):
            return APIResponse.error(
                message="Vous n'êtes pas l'organisateur de cet événement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        stats = get_event_payment_stats(event)
        serializer = PaymentStatsSerializer(stats)

        return APIResponse.success(
            data=serializer.data,
            message=f"Statistiques de '{event.title}'.",
        )


# ==================================================================
# SIMULATION (DEVELOPMENT ONLY)
# ==================================================================
class PaymentSimulateView(APIView):
    """
    POST /api/payments/development/{id}/simulate/

    ⚠️ Uniquement disponible en développement.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not settings.PAYMENT_DEVELOPMENT_ENABLED:
            return APIResponse.error(
                message="La simulation est désactivée.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        payment = get_object_or_404(Payment, pk=pk)
        self.check_object_permissions(request, payment)

        serializer = SimulatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Données invalides.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payment = PaymentService.simulate_payment_result(
            payment=payment,
            result=serializer.validated_data["result"],
        )

        return APIResponse.success(
            data=PaymentDetailSerializer(payment, context={"request": request}).data,
            message=f"Résultat simulé : {payment.status}.",
        )


# ==================================================================
# WEBHOOK (placeholder V2)
# ==================================================================
class PaymentWebhookView(APIView):
    """
    POST /api/payments/webhooks/{provider}/

    ⚠️ Placeholder V2 : pas encore implémenté.
    """

    permission_classes = [AllowAny]

    def post(self, request, provider):
        return APIResponse.error(
            message=f"Les webhooks du provider '{provider}' ne sont pas encore disponibles.",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )