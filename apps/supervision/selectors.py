"""
Selectors du module Supervision : lectures en base.

Phase S1 : journal d'audit.
Phase S2 : utilisateurs, activité d'un utilisateur, organisateurs.
Phase S3 : événements et catégories.
Phase S4 : inscriptions et présences (lecture seule).

Les compteurs sont calculés en SQL par des SOUS-REQUÊTES (une par compteur)
plutôt que par des jointures + COUNT : avec plusieurs jointures, les lignes
se multiplient et les totaux deviennent faux (ex. 3 événements x 4 inscrits
= 12 lignes). La sous-requête compte chaque table séparément.
"""

from django.db.models import Count, IntegerField, OuterRef, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.constants import ROLE_ORGANIZER
from apps.accounts.models import User
from apps.attendance.constants import AttendanceStatus
from apps.attendance.models import Attendance
from apps.events.constants import EventStatus
from apps.events.models import Category, Event
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.supervision.constants import ACTIVITY_PREVIEW_SIZE
from apps.supervision.models import AuditLog

ACTIVE_REGISTRATION_STATUSES = (RegistrationStatus.PENDING, RegistrationStatus.CONFIRMED)


# ==================================================================
# OUTIL : compteur par sous-requête
# ==================================================================
def _count_of(queryset, link_field: str):
    """
    Compte les lignes de `queryset` rattachées à l'objet de la ligne courante.

    Exemples :
        _count_of(Event.objects.all(), "organizer")
            → sur une liste d'utilisateurs : nombre d'événements organisés ;
        _count_of(Registration.objects.all(), "event")
            → sur une liste d'événements : nombre d'inscriptions.
    Coalesce(..., 0) renvoie 0 au lieu de NULL quand il n'y a rien.
    """
    subquery = (
        queryset.filter(**{link_field: OuterRef("pk")})
        .order_by()
        .values(link_field)
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )
    return Coalesce(Subquery(subquery, output_field=IntegerField()), 0)


# ==================================================================
# JOURNAL D'AUDIT (S1)
# ==================================================================
def get_audit_logs() -> QuerySet[AuditLog]:
    """Toutes les entrées, les plus récentes d'abord, acteur préchargé."""
    return AuditLog.objects.select_related("actor").order_by("-created_at")


def get_audit_log_by_id(audit_log_id) -> AuditLog | None:
    return AuditLog.objects.select_related("actor").filter(id=audit_log_id).first()


# ==================================================================
# UTILISATEURS (S2)
# ==================================================================
def get_supervision_users() -> QuerySet[User]:
    """Tous les comptes, rôles préchargés (1 requête pour tous les rôles)."""
    return User.objects.prefetch_related("roles").order_by("-created_at")


def get_supervision_user_detail(user_id) -> User | None:
    """Un compte avec ses compteurs d'activité, ou None."""
    return (
        User.objects.prefetch_related("roles")
        .annotate(
            organized_events_count=_count_of(Event.objects.all(), "organizer"),
            active_registrations_count=_count_of(
                Registration.objects.filter(status__in=ACTIVE_REGISTRATION_STATUSES),
                "participant",
            ),
            attendances_present_count=_count_of(
                Attendance.objects.filter(status=AttendanceStatus.PRESENT),
                "registration__participant",
            ),
        )
        .filter(pk=user_id)
        .first()
    )


def get_user_activity(user) -> dict:
    """
    Aperçu de l'activité d'un compte : les éléments les plus récents de
    chaque rubrique + le total réel de chaque rubrique.
    """
    events = Event.objects.filter(organizer=user).select_related("category")
    registrations = Registration.objects.filter(participant=user).select_related("event")
    attendances = Attendance.objects.filter(
        registration__participant=user,
    ).select_related("registration__event")

    return {
        "organized_events": {
            "total": events.count(),
            "recent": list(events.order_by("-start_at")[:ACTIVITY_PREVIEW_SIZE]),
        },
        "registrations": {
            "total": registrations.count(),
            "recent": list(registrations.order_by("-registered_at")[:ACTIVITY_PREVIEW_SIZE]),
        },
        "attendances": {
            "total": attendances.count(),
            "recent": list(attendances.order_by("-created_at")[:ACTIVITY_PREVIEW_SIZE]),
        },
    }


# ==================================================================
# ORGANISATEURS (S2)
# ==================================================================
def get_organizers() -> QuerySet[User]:
    """
    Les comptes ayant le rôle « organisateur », avec leurs compteurs :
        events_total            : tous leurs événements (brouillons compris)
        events_published        : statut PUBLISHED
        events_upcoming         : publiés ET pas encore commencés
        events_cancelled        : statut CANCELLED
        registrations_confirmed : inscriptions confirmées à leurs événements
    """
    now = timezone.now()
    return (
        User.objects.filter(roles__name=ROLE_ORGANIZER)
        .prefetch_related("roles")
        .annotate(
            events_total=_count_of(Event.objects.all(), "organizer"),
            events_published=_count_of(
                Event.objects.filter(status=EventStatus.PUBLISHED), "organizer",
            ),
            events_upcoming=_count_of(
                Event.objects.filter(status=EventStatus.PUBLISHED, start_at__gt=now),
                "organizer",
            ),
            events_cancelled=_count_of(
                Event.objects.filter(status=EventStatus.CANCELLED), "organizer",
            ),
            registrations_confirmed=_count_of(
                Registration.objects.filter(status=RegistrationStatus.CONFIRMED),
                "event__organizer",
            ),
        )
        .order_by("-created_at")
    )


def get_organizer_by_id(user_id) -> User | None:
    """Un organisateur avec ses compteurs, ou None (inexistant ou pas organisateur)."""
    return get_organizers().filter(pk=user_id).first()


# ==================================================================
# ÉVÉNEMENTS (S3)
# ==================================================================
def get_supervision_events() -> QuerySet[Event]:
    """
    Tous les événements (tous statuts), organisateur et catégorie préchargés,
    avec le nombre d'inscrits confirmés et de présents.
    """
    return (
        Event.objects.select_related("organizer", "category")
        .annotate(
            registrations_confirmed=_count_of(
                Registration.objects.filter(status=RegistrationStatus.CONFIRMED), "event",
            ),
            attendances_present=_count_of(
                Attendance.objects.filter(status=AttendanceStatus.PRESENT), "registration__event",
            ),
        )
        .order_by("-start_at")
    )


def get_supervision_event_detail(event_id) -> Event | None:
    """Un événement avec, en plus, les inscriptions en attente et annulées."""
    return (
        get_supervision_events()
        .annotate(
            registrations_pending=_count_of(
                Registration.objects.filter(status=RegistrationStatus.PENDING), "event",
            ),
            registrations_cancelled=_count_of(
                Registration.objects.filter(status=RegistrationStatus.CANCELLED), "event",
            ),
        )
        .filter(pk=event_id)
        .first()
    )


# ==================================================================
# CATÉGORIES (S3)
# ==================================================================
def get_supervision_categories() -> QuerySet[Category]:
    """Toutes les catégories (actives ou non) avec leur nombre d'événements."""
    return (
        Category.objects.annotate(
            events_total=_count_of(Event.objects.all(), "category"),
            events_published=_count_of(
                Event.objects.filter(status=EventStatus.PUBLISHED), "category",
            ),
        )
        .order_by("name")
    )


def get_supervision_category_by_id(category_id) -> Category | None:
    return get_supervision_categories().filter(pk=category_id).first()


# ==================================================================
# INSCRIPTIONS (S4)
# ==================================================================
def get_supervision_registrations() -> QuerySet[Registration]:
    """
    Toutes les inscriptions (tous statuts, tous événements).
    La fiche de présence éventuelle est chargée dans la MÊME requête
    (jointure gauche : attendance vaut None si le participant n'est pas venu).
    """
    return (
        Registration.objects.select_related(
            "participant",
            "event",
            "event__organizer",
            "attendance",
            "attendance__recorded_by",
        )
        .order_by("-registered_at")
    )


def get_supervision_registration_by_id(registration_id) -> Registration | None:
    return get_supervision_registrations().filter(pk=registration_id).first()


# ==================================================================
# PRÉSENCES (S4)
# ==================================================================
def get_supervision_attendances() -> QuerySet[Attendance]:
    """Toutes les fiches de présence, tous événements confondus."""
    return (
        Attendance.objects.select_related(
            "registration",
            "registration__participant",
            "registration__event",
            "recorded_by",
        )
        .order_by("-created_at")
    )
