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


# ------------------------------------------------------------------
# Permissions du module Event (compléments)
# ------------------------------------------------------------------
PERM_EVENT_VIEW = "event.view"
PERM_EVENT_CANCEL = "event.cancel"
PERM_EVENT_VIEW_ALL = "event.view_all"
PERM_EVENT_MANAGE_CATEGORY = "event.manage_category"

# Liste complète des permissions Event (pour la création initiale)
ALL_EVENT_PERMISSIONS = (
    (PERM_EVENT_CREATE, "Créer un événement"),
    (PERM_EVENT_VIEW, "Consulter un événement"),
    (PERM_EVENT_UPDATE, "Modifier un événement"),
    (PERM_EVENT_DELETE, "Supprimer un événement"),
    (PERM_EVENT_PUBLISH, "Publier un événement"),
    (PERM_EVENT_CANCEL, "Annuler un événement"),
    (PERM_EVENT_VIEW_PARTICIPANTS, "Voir les participants d'un événement"),
    (PERM_EVENT_VIEW_ALL, "Voir tous les événements (admin)"),
    (PERM_EVENT_MANAGE_CATEGORY, "Gérer les catégories d'événements"),
)


# ------------------------------------------------------------------
# Permissions du module Registration
# ------------------------------------------------------------------
PERM_REGISTRATION_CREATE = "registration.create"
PERM_REGISTRATION_VIEW_OWN = "registration.view_own"
PERM_REGISTRATION_CANCEL_OWN = "registration.cancel_own"
PERM_REGISTRATION_VIEW_EVENT = "registration.view_event"
PERM_REGISTRATION_CONFIRM = "registration.confirm"
PERM_REGISTRATION_CANCEL = "registration.cancel"
PERM_REGISTRATION_VIEW_ALL = "registration.view_all"

ALL_REGISTRATION_PERMISSIONS = (
    (PERM_REGISTRATION_CREATE, "Créer une inscription"),
    (PERM_REGISTRATION_VIEW_OWN, "Voir ses propres inscriptions"),
    (PERM_REGISTRATION_CANCEL_OWN, "Annuler ses propres inscriptions"),
    (PERM_REGISTRATION_VIEW_EVENT, "Voir les inscriptions d'un événement"),
    (PERM_REGISTRATION_CONFIRM, "Confirmer une inscription"),
    (PERM_REGISTRATION_CANCEL, "Annuler une inscription (organisateur)"),
    (PERM_REGISTRATION_VIEW_ALL, "Voir toutes les inscriptions (admin)"),
)