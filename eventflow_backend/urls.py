"""
Routes URL racine du projet EVENTFLOW.

Deux réglages (voir settings.py) :
    - ADMIN_URL        : chemin de l'admin Django (ex: "gestion-x7k2q9/").
                         Doit finir par "/" et ne pas commencer par "/".
    - API_DOCS_ENABLED : expose /api/schema/ et /api/docs/ (désactivé par
                         défaut hors DEBUG, car ils décrivent toute l'API).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin Django (chemin configurable)
    path(getattr(settings, "ADMIN_URL", "admin/"), admin.site.urls),

    # API EVENTFLOW
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.events.urls")),
    path("api/", include("apps.registrations.urls")),
    path("api/", include("apps.payments.urls")),
    path("api/", include("apps.attendance.urls")),
    path("api/supervision/", include("apps.supervision.urls")),
    path("api/", include("apps.dashboards.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/", include("apps.tickets.urls")),
    path("api/", include("apps.certificates.urls")),
]

# Documentation API : seulement si activée
if getattr(settings, "API_DOCS_ENABLED", settings.DEBUG):
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]

# Fichiers statiques et médias servis par Django en développement uniquement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)