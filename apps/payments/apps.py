from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Configuration de l'application 'payments'."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.payments'
    verbose_name = "Gestion des paiements"