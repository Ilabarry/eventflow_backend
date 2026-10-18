"""
Selectors du module Payment.
"""

from django.db.models import Count, Q, Sum
from django.db.models import QuerySet

from apps.accounts.constants import ROLE_ADMIN
from apps.payments.constants import PaymentStatus
from apps.payments.models import Payment


# ==================================================================
# LECTURE PAR ID
# ==================================================================
def get_payment_by_id(payment_id) -> Payment | None:
    """Retourne un paiement par son UUID, avec relations préchargées."""
    return (
        Payment.objects
        .select_related(
            "registration",
            "registration__participant",
            "registration__event",
            "registration__event__organizer",
        )
        .filter(id=payment_id)
        .first()
    )


# ==================================================================
# LECTURES PAR CONTEXTE
# ==================================================================
def get_user_payments(user) -> QuerySet[Payment]:
    """Paiements d'un utilisateur (via ses inscriptions)."""
    return (
        Payment.objects
        .filter(registration__participant=user)
        .select_related("registration", "registration__event")
        .order_by("-created_at")
    )


def get_registration_payments(registration) -> QuerySet[Payment]:
    """Paiements d'une inscription."""
    return (
        Payment.objects
        .filter(registration=registration)
        .order_by("-created_at")
    )


def get_event_payments(event) -> QuerySet[Payment]:
    """Paiements liés aux inscriptions d'un événement."""
    return (
        Payment.objects
        .filter(registration__event=event)
        .select_related("registration", "registration__participant")
        .order_by("-created_at")
    )


def get_all_payments() -> QuerySet[Payment]:
    """Tous les paiements (admin)."""
    return (
        Payment.objects
        .all()
        .select_related(
            "registration",
            "registration__participant",
            "registration__event",
        )
        .order_by("-created_at")
    )


def get_payments_for_user(user) -> QuerySet[Payment]:
    """
    Paiements visibles par un utilisateur.

    - Admin : tous
    - Organisateur : ses paiements + ceux de ses événements
    - Participant : ses paiements
    """
    if not user or not user.is_authenticated:
        return Payment.objects.none()

    if user.is_superuser or user.is_staff or user.has_role(ROLE_ADMIN):
        return get_all_payments()

    from apps.accounts.constants import ROLE_ORGANIZER
    if user.has_role(ROLE_ORGANIZER):
        return (
            Payment.objects
            .filter(
                Q(registration__participant=user)
                | Q(registration__event__organizer=user)
            )
            .select_related("registration", "registration__event", "registration__participant")
            .distinct()
            .order_by("-created_at")
        )

    return get_user_payments(user)


# ==================================================================
# STATISTIQUES POUR UN ÉVÉNEMENT
# ==================================================================
def get_event_payment_stats(event) -> dict:
    """
    Calcule les statistiques de paiement pour un événement.

    Returns:
        dict avec :
            - total_transactions
            - successful / pending / failed / cancelled / refunded
            - total_amount (uniquement SUCCESS)
            - refunded_amount (uniquement REFUNDED)
            - currency
    """
    from django.db.models import Count, Q, Sum

    qs = Payment.objects.filter(registration__event=event)

    # Compteurs par statut
    counts = qs.aggregate(
        total=Count("id"),
        successful=Count("id", filter=Q(status=PaymentStatus.SUCCESS)),
        pending=Count("id", filter=Q(status=PaymentStatus.PENDING)),
        failed=Count("id", filter=Q(status=PaymentStatus.FAILED)),
        cancelled=Count("id", filter=Q(status=PaymentStatus.CANCELLED)),
        refunded=Count("id", filter=Q(status=PaymentStatus.REFUNDED)),
    )

    # Montants
    total_amount = qs.filter(status=PaymentStatus.SUCCESS).aggregate(
        total=Sum("amount")
    )["total"] or 0

    refunded_amount = qs.filter(status=PaymentStatus.REFUNDED).aggregate(
        total=Sum("amount")
    )["total"] or 0

    return {
        "total_transactions": counts["total"],
        "successful": counts["successful"],
        "pending": counts["pending"],
        "failed": counts["failed"],
        "cancelled": counts["cancelled"],
        "refunded": counts["refunded"],
        "total_amount": total_amount,
        "refunded_amount": refunded_amount,
        "currency": "XOF",
    }