"""
Routes URL racine du projet EVENTFLOW.
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
    # Admin Django
    path("admin/", admin.site.urls),

    # Documentation API
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

