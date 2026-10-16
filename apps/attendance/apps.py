from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    """Configuration de l'application 'attendance'."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.attendance'
    verbose_name = "Gestion des présences"
