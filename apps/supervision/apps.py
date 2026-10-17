from django.apps import AppConfig


class SupervisionConfig(AppConfig):
    """Configuration de l'application 'supervision' (administration)."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.supervision'
    verbose_name = "Supervision et audit"
