"""
Routes URL du module Payment.
"""

from django.urls import path

from apps.payments.views import (
    EventPaymentsView,
    EventPaymentStatsView,
    InitiatePaymentView,
    MyPaymentsView,
    PaymentCancelView,
    PaymentDetailView,
    PaymentRefundView,
    PaymentSimulateView,
    PaymentStatusView,
    PaymentWebhookView,
    RegistrationPaymentsView,
)

app_name = "payments"

urlpatterns = [
    # Participant
    path("payments/initiate/", InitiatePaymentView.as_view(), name="payment-initiate"),
    path("payments/me/", MyPaymentsView.as_view(), name="payment-my"),
    path("payments/<uuid:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/<uuid:pk>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("payments/<uuid:pk>/cancel/", PaymentCancelView.as_view(), name="payment-cancel"),
    path("payments/<uuid:pk>/refund/", PaymentRefundView.as_view(), name="payment-refund"),

    # Inscriptions
    path(
        "registrations/<uuid:registration_id>/payments/",
        RegistrationPaymentsView.as_view(),
        name="registration-payments",
    ),

    # Événements (organisateur)
    path(
        "events/<uuid:event_id>/payments/",
        EventPaymentsView.as_view(),
        name="event-payments",
    ),
    path(
        "events/<uuid:event_id>/payments/stats/",
        EventPaymentStatsView.as_view(),
        name="event-payment-stats",
    ),

    # Développement
    path(
        "payments/development/<uuid:pk>/simulate/",
        PaymentSimulateView.as_view(),
        name="payment-simulate",
    ),

    # Webhook placeholder
    path(
        "payments/webhooks/<str:provider>/",
        PaymentWebhookView.as_view(),
        name="payment-webhook",
    ),
]