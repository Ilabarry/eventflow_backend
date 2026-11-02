"""
Throttles personnalisés (limitation de débit).

EmailScopedThrottle limite le nombre de requêtes visant UNE MÊME adresse email,
quelle que soit l'IP de l'appelant. Il complète ScopedRateThrottle (qui compte
par IP ou par utilisateur) et bloque un attaquant qui change d'IP pour viser
un compte précis.

⚠️ Chaque classe lit son taux dans settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
sous la clé `scope`. Si la clé manque, DRF lève ImproperlyConfigured (erreur 500).
"""

import hashlib

from rest_framework.throttling import SimpleRateThrottle


class EmailScopedThrottle(SimpleRateThrottle):
    """Limite par email ciblé (login). Clé de taux : 'auth_login_email'."""

    scope = "auth_login_email"

    def get_cache_key(self, request, view):
        data = request.data
        email = ""
        if hasattr(data, "get"):
            value = data.get("email", "")
            if isinstance(value, str):
                email = value.lower().strip()

        # Pas d'email exploitable : on ne limite pas ici (le serializer répondra 400)
        if not email:
            return None

        # Hash : évite les caractères spéciaux dans la clé de cache
        ident = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ResendEmailTargetThrottle(EmailScopedThrottle):
    """Limite par email ciblé (renvoi de l'email de vérification). Clé : 'auth_email_target'."""

    scope = "auth_email_target"