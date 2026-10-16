"""
Validateurs métier du module Attendance.

Chaque fonction vérifie UNE règle et lève une exception métier
explicite si elle n'est pas respectée. Les messages sont pensés
pour être affichés tels quels par Angular.

Ces fonctions ne touchent pas à la base : elles sont faciles à
tester et réutilisables (check-in manuel, check-in QR, absence).
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.attendance.constants import CheckInMethod
from apps.attendance.permissions import can_manage_event_attendance
from apps.events.constants import EventStatus
from apps.registrations.constants import RegistrationStatus
from common.exceptions.business import (
    BusinessException,
    CheckInNotOpen,
    EventCancelled,
    EventCompleted,
    EventNotPublished,
    RegistrationNotEligibleForCheckIn,
    UnauthorizedEventAccess,
)

DATETIME_FORMAT = "%d/%m/%Y à %H:%M"


def _format_local(dt) -> str:
    """Affiche une date dans le fuseau du projet (TIME_ZONE)."""
    return timezone.localtime(dt).strftime(DATETIME_FORMAT)


# ------------------------------------------------------------------
# Autorisation
# ------------------------------------------------------------------
def ensure_can_manage_event(user, event) -> None:
    """Refuse l'action si l'utilisateur n'est ni organisateur ni admin."""
    if not can_manage_event_attendance(user, event):
        raise UnauthorizedEventAccess(
            detail="Vous n'êtes pas l'organisateur de cet événement."
        )


# ------------------------------------------------------------------
# Inscription
# ------------------------------------------------------------------
def validate_registration_for_attendance(registration) -> None:
    """
    Seule une inscription CONFIRMED peut recevoir une fiche de présence.

    - CANCELLED : le participant n'est plus inscrit.
    - PENDING   : inscription non validée (paiement en attente).
    """
    if registration.status == RegistrationStatus.CANCELLED:
        raise RegistrationNotEligibleForCheckIn(
            detail="Cette inscription a été annulée."
        )
    if registration.status == RegistrationStatus.PENDING:
        raise RegistrationNotEligibleForCheckIn(
            detail="Cette inscription n'est pas encore confirmée."
        )


# ------------------------------------------------------------------
# Événement
# ------------------------------------------------------------------
def _validate_event_status(event, *, allow_completed: bool) -> None:
    """Vérifie que le statut de l'événement autorise l'action."""
    if event.status == EventStatus.DRAFT:
        raise EventNotPublished(detail="Cet événement n'est pas publié.")
    if event.status == EventStatus.CANCELLED:
        raise EventCancelled()
    if event.status == EventStatus.COMPLETED and not allow_completed:
        raise EventCompleted()


def get_check_in_opening(event):
    """Date à partir de laquelle le check-in est ouvert."""
    minutes = settings.ATTENDANCE_CHECK_IN_OPENS_BEFORE_MINUTES
    return event.start_at - timedelta(minutes=minutes)


def validate_event_for_check_in(event, now=None) -> None:
    """
    Le check-in est possible si l'événement est PUBLISHED et si l'on se
    trouve entre (début - délai d'ouverture) et la fin de l'événement.
    """
    now = now or timezone.now()
    _validate_event_status(event, allow_completed=False)

    opening = get_check_in_opening(event)
    if now < opening:
        raise CheckInNotOpen(
            detail=f"Le check-in ouvrira le {_format_local(opening)}."
        )
    if now > event.end_at:
        raise CheckInNotOpen(
            detail="Le check-in est fermé : l'événement est terminé."
        )


def validate_event_for_absence(event, now=None) -> None:
    """
    On ne peut déclarer un participant absent qu'une fois l'événement
    commencé. Un événement COMPLETED reste autorisé (bilan après coup).
    """
    now = now or timezone.now()
    _validate_event_status(event, allow_completed=True)

    if now < event.start_at:
        raise CheckInNotOpen(
            detail="Un participant ne peut être déclaré absent "
                   "qu'après le début de l'événement."
        )


# ------------------------------------------------------------------
# Méthode de check-in
# ------------------------------------------------------------------
def validate_check_in_method(method: str) -> None:
    """Refuse toute méthode inconnue (protection contre une valeur forgée)."""
    if method not in CheckInMethod.values:
        raise BusinessException(detail="Méthode de check-in invalide.")
