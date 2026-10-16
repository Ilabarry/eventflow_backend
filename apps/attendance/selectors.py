"""
Selectors du module Attendance : toutes les LECTURES en base.

Chaque requête précharge les relations utilisées par les serializers
(select_related), pour éviter le problème N+1 :
sans cela, afficher 50 présences déclencherait 1 + 50 x 3 requêtes SQL.
"""

from django.db.models import QuerySet

from apps.attendance.models import Attendance

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
