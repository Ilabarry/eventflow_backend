"""
Limitation du débit des routes de supervision.

Deux scopes, réglés dans settings.py (REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']) :
    - supervision_read   : consultations (listes, statistiques) ;
    - supervision_action : actions sensibles (suspendre, annuler...).

Le débit est compté PAR UTILISATEUR : un admin dont le compte serait
compromis ne peut pas aspirer la base ni enchaîner des milliers d'actions.
"""

from rest_framework.settings import api_settings
from rest_framework.throttling import UserRateThrottle

from apps.supervision.constants import THROTTLE_SCOPE_ACTION, THROTTLE_SCOPE_READ


class _SettingsRateThrottle(UserRateThrottle):
    """Relit le débit dans les réglages à chaque appel (utile aux tests)."""

    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)


class SupervisionReadThrottle(_SettingsRateThrottle):
    scope = THROTTLE_SCOPE_READ


class SupervisionActionThrottle(_SettingsRateThrottle):
    scope = THROTTLE_SCOPE_ACTION
