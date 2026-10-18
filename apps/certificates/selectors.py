"""
Selectors du module Certificates : toutes les LECTURES en base.
"""

from django.db.models import Count, Q, QuerySet

from apps.accounts.constants import ROLE_ADMIN
from apps.certificates.constants import CertificateStatus
from apps.certificates.models import Certificate


def get_certificate_by_id(certificate_id) -> Certificate | None:
    return (
        Certificate.objects
        .select_related(
            "registration",
            "registration__participant",
            "registration__event",
            "registration__event__organizer",
        )
        .filter(id=certificate_id)
        .first()
    )


def get_user_certificates(user) -> QuerySet[Certificate]:
    return (
        Certificate.objects
        .filter(registration__participant=user)
        .select_related("registration", "registration__event")
        .order_by("-issued_at")
    )


def get_event_certificates(event) -> QuerySet[Certificate]:
    return (
        Certificate.objects
        .filter(registration__event=event)
        .select_related("registration", "registration__participant")
        .order_by("-issued_at")
    )


def get_all_certificates() -> QuerySet[Certificate]:
    return (
        Certificate.objects
        .all()
        .select_related("registration", "registration__event", "registration__participant")
        .order_by("-issued_at")
    )


def get_event_certificate_stats(event) -> dict:
    """Statistiques des certificats d'un événement."""
    from apps.registrations.constants import RegistrationStatus
    from apps.registrations.models import Registration

    total_registered = Registration.objects.filter(
        event=event, status=RegistrationStatus.CONFIRMED
    ).count()

    qs = Certificate.objects.filter(registration__event=event)
    counts = qs.aggregate(
        issued=Count("id", filter=Q(status=CertificateStatus.ISSUED)),
        revoked=Count("id", filter=Q(status=CertificateStatus.REVOKED)),
        pending=Count("id", filter=Q(status=CertificateStatus.PENDING)),
    )

    return {
        "total_registered": total_registered,
        "issued": counts["issued"],
        "revoked": counts["revoked"],
        "pending": counts["pending"],
        "not_generated": total_registered - (counts["issued"] + counts["revoked"] + counts["pending"]),
    }