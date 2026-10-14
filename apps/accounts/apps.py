from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Configuration de l'application 'accounts'.

    Note : plus de méthode ready() car on a supprimé les signals.
    Le rôle est désormais attribué explicitement par le service d'inscription.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = "Gestion des comptes"