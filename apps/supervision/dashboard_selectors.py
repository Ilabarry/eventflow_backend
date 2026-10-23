"""
Lectures agrégées du module Supervision (phase S6) :
tableau de bord, statistiques et alertes.

Séparées de selectors.py pour garder chaque fichier lisible : ici, on
ne renvoie pas des listes d'objets mais des CHIFFRES calculés en SQL.

Principe : chaque bloc de chiffres = UNE requête, grâce à
    aggregate(nom=Count("pk", filter=Q(...)))
qui se traduit en SQL par COUNT(*) FILTER (WHERE ...). Le nombre de
requêtes reste donc le même avec 10 ou 100 000 lignes en base.
Rien n'est stocké : tout est recalculé à chaque appel.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN, ROLE_ORGANIZER, ROLE_PARTICIPANT
from apps.accounts.models import User
from apps.attendance.constants import AttendanceStatus
from apps.attendance.models import Attendance
from apps.events.constants import EventStatus
from apps.events.models import Category, Event
from apps.registrations.constants import RegistrationStatus
from apps.registrations.models import Registration
from apps.supervision.constants import (
    ALERT_SAMPLE_SIZE,
    ALERT_SECURITY_WINDOW_HOURS,
    ALERT_STALE_PENDING_DAYS,
    ALERT_UPCOMING_WINDOW_DAYS,
    DASHBOARD_AUDIT_WINDOW_DAYS,
    DASHBOARD_NEW_USERS_DAYS,
    STATS_TOP_CITIES,
    AlertLevel,
    AuditResult,
)
from apps.supervision.models import AuditLog


def _rate(part: int, total: int) -> float:
    """Pourcentage arrondi à 0,1 ; 0.0 si total = 0 (pas de division par zéro)."""
    return round(part / total * 100, 1) if total else 0.0


# ==================================================================
# TABLEAU DE BORD
# ==================================================================
def get_dashboard_overview() -> dict:
    """Chiffres clés de la plateforme, à l'instant présent."""
    now = timezone.now()

    # distinct=True : la jointure avec les rôles peut dupliquer un compte
    # qui a plusieurs rôles ; on ne veut le compter qu'une fois.
    users = User.objects.aggregate(
        total=Count("pk", distinct=True),
        active=Count("pk", filter=Q(is_active=True), distinct=True),
        suspended=Count("pk", filter=Q(is_active=False), distinct=True),
        participants=Count("pk", filter=Q(roles__name=ROLE_PARTICIPANT), distinct=True),
        organizers=Count("pk", filter=Q(roles__name=ROLE_ORGANIZER), distinct=True),
        admins=Count(
            "pk",
            filter=Q(is_superuser=True) | Q(is_staff=True) | Q(roles__name=ROLE_ADMIN),
            distinct=True,
        ),
        new_last_30_days=Count(
            "pk",
            filter=Q(created_at__gte=now - timedelta(days=DASHBOARD_NEW_USERS_DAYS)),
            distinct=True,
        ),
    )

    events = Event.objects.aggregate(
        total=Count("pk"),
        draft=Count("pk", filter=Q(status=EventStatus.DRAFT)),
        published=Count("pk", filter=Q(status=EventStatus.PUBLISHED)),
        completed=Count("pk", filter=Q(status=EventStatus.COMPLETED)),
        cancelled=Count("pk", filter=Q(status=EventStatus.CANCELLED)),
        upcoming=Count("pk", filter=Q(status=EventStatus.PUBLISHED, start_at__gt=now)),
    )

    registrations = Registration.objects.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status=RegistrationStatus.PENDING)),
        confirmed=Count("pk", filter=Q(status=RegistrationStatus.CONFIRMED)),
        cancelled=Count("pk", filter=Q(status=RegistrationStatus.CANCELLED)),
        # « attendus » = confirmés sur des événements déjà commencés
        expected=Count(
            "pk",
            filter=Q(status=RegistrationStatus.CONFIRMED, event__start_at__lte=now),
        ),
    )

    attendance = Attendance.objects.aggregate(
        present=Count("pk", filter=Q(status=AttendanceStatus.PRESENT)),
        absent=Count("pk", filter=Q(status=AttendanceStatus.ABSENT)),
    )
    expected = registrations.pop("expected")
    attendance["expected"] = expected
    attendance["attendance_rate"] = _rate(attendance["present"], expected)

    categories = Category.objects.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        inactive=Count("pk", filter=Q(is_active=False)),
    )

    audit = AuditLog.objects.filter(
        created_at__gte=now - timedelta(days=DASHBOARD_AUDIT_WINDOW_DAYS),
    ).aggregate(
        actions_last_7_days=Count("pk"),
        denied_last_7_days=Count("pk", filter=Q(result=AuditResult.DENIED)),
    )

    return {
        "generated_at": now,
        "users": users,
        "events": events,
        "registrations": registrations,
        "attendance": attendance,
        "categories": categories,
        "audit": audit,
    }


# ==================================================================
# STATISTIQUES
# ==================================================================
def _month_starts(months: int) -> list:
    """
    Les 1ers jours des `months` derniers mois (mois en cours inclus),
    dans le fuseau du projet (Africa/Dakar).
    Exemple (octobre 2026, months=3) : [1er août, 1er sept., 1er oct.]
    """
    current = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    starts = [current]
    for _ in range(months - 1):
        previous = (starts[0] - timedelta(days=1)).replace(day=1)
        starts.insert(0, previous)
    return starts


def _monthly_counts(queryset, date_field: str, since) -> dict:
    """{'2026-10': 12, ...} : nombre de lignes par mois depuis `since`."""
    rows = (
        queryset.filter(**{f"{date_field}__gte": since})
        .annotate(month=TruncMonth(date_field))
        .values("month")
        .annotate(total=Count("pk"))
    )
    return {timezone.localtime(row["month"]).strftime("%Y-%m"): row["total"] for row in rows}


def get_platform_statistics(months: int) -> dict:
    """
    Évolution mois par mois et répartitions.

    Les mois sans activité apparaissent avec 0 : le graphique côté
    Angular n'aura pas de « trou » dans l'axe du temps.
    """
    starts = _month_starts(months)
    since = starts[0]

    series = {
        "new_users": _monthly_counts(User.objects.all(), "created_at", since),
        "events_created": _monthly_counts(Event.objects.all(), "created_at", since),
        "registrations": _monthly_counts(Registration.objects.all(), "registered_at", since),
        "check_ins": _monthly_counts(
            Attendance.objects.filter(status=AttendanceStatus.PRESENT), "checked_in_at", since,
        ),
    }
    monthly = []
    for start in starts:
        key = start.strftime("%Y-%m")
        monthly.append({"month": key, **{name: values.get(key, 0) for name, values in series.items()}})

    # « events » est déjà le nom de la relation Category → Event : le compteur
    # s'appelle donc events_total en SQL, puis « events » dans la réponse.
    events_by_category = [
        {"id": row["id"], "name": row["name"], "events": row["events_total"]}
        for row in Category.objects.annotate(events_total=Count("events"))
        .filter(events_total__gt=0)
        .order_by("-events_total", "name")
        .values("id", "name", "events_total")
    ]
    events_by_city = list(
        Event.objects.exclude(city="")
        .values("city")
        .annotate(events=Count("pk"))
        .order_by("-events", "city")[:STATS_TOP_CITIES]
    )
    events_by_format = list(
        Event.objects.values("format").annotate(events=Count("pk")).order_by("-events")
    )
    registrations_by_status = list(
        Registration.objects.values("status").annotate(total=Count("pk")).order_by("status")
    )

    return {
        "months": months,
        "since": since.date(),
        "monthly": monthly,
        "events_by_category": events_by_category,
        "events_by_city": events_by_city,
        "events_by_format": events_by_format,
        "registrations_by_status": registrations_by_status,
    }


# ==================================================================
# ALERTES
# ==================================================================
def _alert(code, level, message, queryset, fields):
    """
    Construit une alerte si `queryset` contient au moins une ligne.
    Renvoie None sinon (l'alerte n'est pas affichée).
    """
    count = queryset.count()
    if count == 0:
        return None
    return {
        "code": code,
        "level": level,
        "message": message,
        "count": count,
        "samples": list(queryset.values(*fields)[:ALERT_SAMPLE_SIZE]),
    }


def get_alerts() -> list[dict]:
    """
    Situations qui demandent l'attention d'un administrateur.
    Seules les alertes déclenchées sont renvoyées, les plus graves d'abord.
    """
    now = timezone.now()
    candidates = [
        _alert(
            "SECURITY_DENIALS",
            AlertLevel.CRITICAL,
            f"Actions refusées par un garde-fou de sécurité ({ALERT_SECURITY_WINDOW_HOURS} dernières heures).",
            AuditLog.objects.filter(
                result=AuditResult.DENIED,
                created_at__gte=now - timedelta(hours=ALERT_SECURITY_WINDOW_HOURS),
            ).order_by("-created_at"),
            ("id", "actor_email", "action", "entity_id", "created_at"),
        ),
        _alert(
            "ENDED_EVENTS_STILL_PUBLISHED",
            AlertLevel.WARNING,
            "Événements terminés mais toujours au statut « publié ».",
            Event.objects.filter(status=EventStatus.PUBLISHED, end_at__lt=now).order_by("end_at"),
            ("id", "title", "end_at", "organizer__email"),
        ),
        _alert(
            "STALE_PENDING_REGISTRATIONS",
            AlertLevel.WARNING,
            f"Inscriptions en attente depuis plus de {ALERT_STALE_PENDING_DAYS} jours.",
            Registration.objects.filter(
                status=RegistrationStatus.PENDING,
                registered_at__lt=now - timedelta(days=ALERT_STALE_PENDING_DAYS),
            ).order_by("registered_at"),
            ("id", "reference", "registered_at", "event__title", "participant__email"),
        ),
        _alert(
            "UPCOMING_EVENTS_WITHOUT_REGISTRATIONS",
            AlertLevel.INFO,
            f"Événements publiés commençant dans moins de {ALERT_UPCOMING_WINDOW_DAYS} jours, sans aucun inscrit confirmé.",
            Event.objects.filter(
                status=EventStatus.PUBLISHED,
                start_at__gt=now,
                start_at__lte=now + timedelta(days=ALERT_UPCOMING_WINDOW_DAYS),
            )
            .exclude(registrations__status=RegistrationStatus.CONFIRMED)
            .order_by("start_at"),
            ("id", "title", "start_at", "organizer__email"),
        ),
        _alert(
            "SUSPENDED_ACCOUNTS",
            AlertLevel.INFO,
            "Comptes actuellement suspendus.",
            User.objects.filter(is_active=False).order_by("-updated_at"),
            ("id", "email", "updated_at"),
        ),
    ]
    return [alert for alert in candidates if alert is not None]
