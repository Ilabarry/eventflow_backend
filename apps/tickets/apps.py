from django.apps import AppConfig


class TicketsConfig(AppConfig):
    """Configuration de l'application 'tickets'."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tickets'
    verbose_name = "Gestion des billets"