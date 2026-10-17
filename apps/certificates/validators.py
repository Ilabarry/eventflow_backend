"""
Validateurs métier du module Certificates.

Chaque validateur vérifie UNE règle métier et lève une exception
explicite si elle n'est pas respectée.
"""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.attendance.constants import AttendanceStatus
from apps.certificates.constants import CertificateStatus
from apps.certificates.models import Certificate
from apps.events.constants import EventStatus
from apps.registrations.constants import RegistrationStatus
from common.exceptions.business import (
    AttendanceRequired,
    CertificateAlreadyExists,
    CertificateNotEligible,
    EventNotEnded,
)


def validate_registration_for_certificate(registration) -> None:
    """Vérifie que l'inscription est éligible à un certificat."""
    if registration.status == RegistrationStatus.CANCELLED:
        raise CertificateNotEligible(
            detail="Cette inscription a été annulée."
        )
    if registration.status == RegistrationStatus.PENDING:
        raise CertificateNotEligible(
            detail="Cette inscription n'est pas encore confirmée."
        )
    if registration.status != RegistrationStatus.CONFIRMED:
        raise CertificateNotEligible(
            detail=f"Statut d'inscription invalide : {registration.status}."
        )


def validate_event_for_certificate(event) -> None:
    """Vérifie que l'événement est terminé."""
    if event.status == EventStatus.DRAFT:
        raise CertificateNotEligible(
            detail="L'événement n'est pas publié."
        )
    if event.status == EventStatus.CANCELLED:
        raise CertificateNotEligible(
            detail="L'événement a été annulé."
        )
    if event.end_at > timezone.now():
        raise EventNotEnded()


def validate_attendance_for_certificate(registration) -> None:
    """
    Vérifie que le participant a bien assisté à l'événement.

    Attendance est la source de vérité : sans fiche PRESENT, pas de certificat.
    """
    try:
        attendance = registration.attendance
    except Exception:
        raise AttendanceRequired(
            detail="Aucune fiche de présence n'existe pour cette inscription."
        )

    if attendance.status != AttendanceStatus.PRESENT:
        raise AttendanceRequired(
            detail="Le participant n'est pas enregistré comme présent."
        )


def validate_no_existing_certificate(registration) -> None:
    """Vérifie qu'aucun certificat actif n'existe déjà pour cette inscription."""
    if Certificate.objects.filter(
        registration=registration,
        status__in=[CertificateStatus.PENDING, CertificateStatus.ISSUED],
    ).exists():
        raise CertificateAlreadyExists()