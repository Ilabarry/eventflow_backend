"""
Constantes du module dashboards.

Centralise les limites et les choix pour éviter les "magic numbers".
"""

# ------------------------------------------------------------------
# LIMITES DES LISTES
# ------------------------------------------------------------------
UPCOMING_EVENTS_LIMIT = 5
RECENT_REGISTRATIONS_LIMIT = 5
PARTICIPANT_UPCOMING_LIMIT = 5
PARTICIPANT_RECENT_REGISTRATIONS_LIMIT = 5
ADMIN_RECENT_EVENTS_LIMIT = 5
ADMIN_RECENT_USERS_LIMIT = 10

# ------------------------------------------------------------------
# PÉRIODES STATISTIQUES
# ------------------------------------------------------------------
PERIOD_TODAY = "today"
PERIOD_LAST_7_DAYS = "last_7_days"
PERIOD_LAST_30_DAYS = "last_30_days"
PERIOD_LAST_12_MONTHS = "last_12_months"
PERIOD_CUSTOM = "custom"

PERIOD_CHOICES = (
    (PERIOD_TODAY, "Aujourd'hui"),
    (PERIOD_LAST_7_DAYS, "7 derniers jours"),
    (PERIOD_LAST_30_DAYS, "30 derniers jours"),
    (PERIOD_LAST_12_MONTHS, "12 derniers mois"),
    (PERIOD_CUSTOM, "Personnalisé"),
)

DEFAULT_PERIOD = PERIOD_LAST_30_DAYS
MAX_STATISTICS_RANGE_DAYS = 366