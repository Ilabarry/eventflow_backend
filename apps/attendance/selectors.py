"""
Selectors du module Attendance : toutes les LECTURES en base.

Chaque requête précharge les relations utilisées par les serializers
(select_related), pour éviter le problème N+1 :
sans cela, afficher 50 présences déclencherait 1 + 50 x 3 requêtes SQL.
"""

from django.db.models import Count, Q, QuerySet
from django.db.models.functions import TruncHour

from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration

# Relations lues par les serializers (participant, événement, auteur)
_RELATED = (
    "registration",
    "registration__participant",
    "registration__event",
    "recorded_by",
)


def _base_queryset() -> QuerySet[Attendance]:
    return Attendance.objects.select_related(*_RELATED)


def get_attendance_by_id(attendance_id) -> Attendance | None:
    """Une présence par son UUID, ou None."""
    return _base_queryset().filter(id=attendance_id).first()


def get_attendance_by_registration(registration_id) -> Attendance | None:
    """La présence liée à une inscription, ou None (pas encore arrivé)."""
    return _base_queryset().filter(registration_id=registration_id).first()


def get_user_attendances(user) -> QuerySet[Attendance]:
    """Les présences du participant connecté, les plus récentes d'abord."""
    return (
        _base_queryset()
        .filter(registration__participant=user)
        .order_by("-registration__event__start_at")
    )


# ------------------------------------------------------------------
# ORGANISATEUR : liste d'accueil et statistiques d'un événement
# ------------------------------------------------------------------
def get_event_attendance_list(event) -> QuerySet[Registration]:
    """
    Les inscriptions CONFIRMÉES de l'événement, chacune avec sa fiche
    de présence éventuelle (jointure gauche : attendance peut être None).

    Seules les inscriptions confirmées sont « attendues » : les
    inscriptions annulées ou en attente de paiement n'y figurent pas.
    """
    return (
        Registration.objects
        .filter(event=event, status=RegistrationStatus.CONFIRMED)
        .select_related("participant", "attendance", "attendance__recorded_by")
        .order_by("participant__last_name", "participant__first_name")
    )


def get_event_attendance_stats(event) -> dict:
    """
    Statistiques de présence d'un événement, calculées en base.

    Définitions (sur les inscriptions CONFIRMÉES uniquement) :
        total_registered = nombre d'inscrits confirmés
        present          = inscrits avec une fiche PRESENT
        absent           = inscrits avec une fiche ABSENT
        not_checked_in   = inscrits sans fiche = total - present - absent
        attendance_rate  = present / total_registered x 100, arrondi à 0,1
                           (0.0 si aucun inscrit : pas de division par zéro)

    Rien n'est stocké : tout est recalculé à chaque appel à partir de
    Registration et Attendance, ce qui évite toute donnée incohérente.
    Une seule requête SQL pour les compteurs (COUNT ... FILTER).
    """
    counts = (
        Registration.objects
        .filter(event=event, status=RegistrationStatus.CONFIRMED)
        .aggregate(
            total_registered=Count("id"),
            present=Count("id", filter=Q(attendance__status=AttendanceStatus.PRESENT)),
            absent=Count("id", filter=Q(attendance__status=AttendanceStatus.ABSENT)),
            manual_check_ins=Count("id", filter=Q(
                attendance__status=AttendanceStatus.PRESENT,
                attendance__check_in_method=CheckInMethod.MANUAL,
            )),
            qr_check_ins=Count("id", filter=Q(
                attendance__status=AttendanceStatus.PRESENT,
                attendance__check_in_method=CheckInMethod.QR_CODE,
            )),
        )
    )
    total = counts["total_registered"]
    present = counts["present"]
    counts["not_checked_in"] = total - present - counts["absent"]
    counts["attendance_rate"] = round(present / total * 100, 1) if total else 0.0

    # Arrivées par heure (pour un graphique côté Angular)
    by_hour = (
        Attendance.objects
        .filter(
            registration__event=event,
            registration__status=RegistrationStatus.CONFIRMED,
            status=AttendanceStatus.PRESENT,
        )
        .annotate(hour=TruncHour("checked_in_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    counts["check_ins_by_hour"] = [
        {"hour": row["hour"], "count": row["count"]} for row in by_hour
    ]
    return counts
