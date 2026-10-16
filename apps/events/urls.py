"""
Routes URL du module Event.
"""

from django.urls import path

from apps.events.views import (
    CategoryDetailView,
    CategoryListCreateView,
    EventCancelView,
    EventDetailView,
    EventListCreateView,
    EventPublishView,
    EventShareView,
    MyEventsView,
)

app_name = "events"

urlpatterns = [
    # Événements
    path("events/", EventListCreateView.as_view(), name="event-list-create"),
    path("events/my/", MyEventsView.as_view(), name="event-my"),
    path("events/<uuid:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<uuid:pk>/publish/", EventPublishView.as_view(), name="event-publish"),
    path("events/<uuid:pk>/cancel/", EventCancelView.as_view(), name="event-cancel"),
    path("events/<uuid:pk>/share/", EventShareView.as_view(), name="event-share"),

    # Catégories
    path("categories/", CategoryListCreateView.as_view(), name="category-list-create"),
    path("categories/<uuid:pk>/", CategoryDetailView.as_view(), name="category-detail"),
]