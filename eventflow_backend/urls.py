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
from django.urls import include, path, re_path
from django.views.static import serve
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

# Fichiers statiques et médias.
# - En développement : helpers Django.
# - En production : les statiques sont servis par WhiteNoise ; les médias
#   (images de couverture, certificats) sont servis par Django car le plan
#   Render gratuit n'expose pas de stockage média persistant/CDN.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
elif not getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""):
    # En production sans stockage externe, les médias restent servis par
    # Django (disque local éphémère sur Render gratuit). Dès qu'un stockage
    # S3 est configuré, les URL pointent directement vers le fournisseur et
    # cette route n'a plus lieu d'être.
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]