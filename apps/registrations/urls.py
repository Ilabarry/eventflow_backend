"""
Routes URL du module Registration.

Note : les routes imbriquées sous /api/events/{event_id}/registrations/
sont définies ici mais seront incluses dans les URLs globales avec
le préfixe /api/events/.
"""

from django.urls import path

from apps.registrations.views import (
    EventRegistrationDetailView,
    EventRegistrationsView,
    MyRegistrationsView,
    RegistrationCancelView,
    RegistrationDetailView,
    RegistrationListCreateView,
)

app_name = "registrations"

urlpatterns = [
    # Participant
    path("registrations/", RegistrationListCreateView.as_view(), name="registration-list-create"),
    path("registrations/my/", MyRegistrationsView.as_view(), name="registration-my"),
    path("registrations/<uuid:pk>/", RegistrationDetailView.as_view(), name="registration-detail"),
    path("registrations/<uuid:pk>/cancel/", RegistrationCancelView.as_view(), name="registration-cancel"),

    # Organisateur (routes imbriquées sous events)
    path(
        "events/<uuid:event_id>/registrations/",
        EventRegistrationsView.as_view(),
        name="event-registrations",
    ),
    path(
        "events/<uuid:event_id>/registrations/<uuid:registration_id>/",
        EventRegistrationDetailView.as_view(),
        name="event-registration-detail",
    ),
]