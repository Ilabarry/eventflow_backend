"""
Constantes métier de l'application 'accounts'.

On centralise ici les noms de rôles, permissions et autres
valeurs utilisées dans le code, pour éviter les chaînes magiques.

Exemple d'utilisation :
    from apps.accounts.constants import ROLE_PARTICIPANT
    user.add_role(ROLE_PARTICIPANT)
"""

# ------------------------------------------------------------------
# Noms des rôles (utilisés comme valeur de Role.name)
# ------------------------------------------------------------------
ROLE_PARTICIPANT = "participant"
ROLE_ORGANIZER = "organisateur"
ROLE_ADMIN = "administrateur"

# Tous les rôles connus (utile pour la validation)
ALL_ROLES = (ROLE_PARTICIPANT, ROLE_ORGANIZER, ROLE_ADMIN)


# ------------------------------------------------------------------
# Rôles autorisés à l'inscription (choix de l'utilisateur)
#
# IMPORTANT : le rôle ADMIN n'est PAS autorisé ici.
# Seul un administrateur existant peut l'attribuer à un autre utilisateur.
# ------------------------------------------------------------------
SIGNUP_ALLOWED_ROLES = (
    ROLE_PARTICIPANT,
    ROLE_ORGANIZER,
)

# Rôle attribué par défaut si aucun n'est fourni
# (utile pour les fixtures, les scripts, le superuser...)
DEFAULT_ROLE_ON_SIGNUP = ROLE_PARTICIPANT


# ------------------------------------------------------------------
# Descriptions des rôles
# Utilisées lors de la création initiale (get_or_create)
# ------------------------------------------------------------------
ROLE_DESCRIPTIONS = {
    ROLE_PARTICIPANT: "Utilisateur qui s'inscrit et participe aux événements.",
    ROLE_ORGANIZER: "Utilisateur qui crée et gère ses propres événements.",
    ROLE_ADMIN: "Administrateur de la plateforme EVENTFLOW.",
}


# ------------------------------------------------------------------
# Codes de permissions (format "ressource.action")
# On ne crée PAS toutes les permissions dès maintenant :
# on définit seulement les conventions. Les permissions seront
# ajoutées au fur et à mesure des fonctionnalités.
# ------------------------------------------------------------------
PERM_EVENT_CREATE = "event.create"
PERM_EVENT_UPDATE = "event.update"
PERM_EVENT_DELETE = "event.delete"
PERM_EVENT_PUBLISH = "event.publish"
PERM_EVENT_VIEW_PARTICIPANTS = "event.view_participants"

PERM_REGISTRATION_CREATE = "registration.create"
PERM_REGISTRATION_CANCEL = "registration.cancel"

PERM_TICKET_CREATE = "ticket.create"
PERM_TICKET_UPDATE = "ticket.update"

PERM_USER_VIEW = "user.view"
PERM_USER_UPDATE = "user.update"
PERM_USER_SUSPEND = "user.suspend"


# ------------------------------------------------------------------
# Longueurs maximales
# ------------------------------------------------------------------
PHONE_MAX_LENGTH = 20
NAME_MAX_LENGTH = 150