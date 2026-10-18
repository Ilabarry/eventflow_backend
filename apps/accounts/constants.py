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



# ------------------------------------------------------------------
# Permissions du module Payment
# ------------------------------------------------------------------
PERM_PAYMENT_VIEW = "payment.view"
PERM_PAYMENT_INITIATE = "payment.initiate"
PERM_PAYMENT_CANCEL = "payment.cancel"
PERM_PAYMENT_REFUND = "payment.refund"
PERM_PAYMENT_MANAGE = "payment.manage"
PERM_PAYMENT_VIEW_STATS = "payment.view_stats"

ALL_PAYMENT_PERMISSIONS = (
    (PERM_PAYMENT_VIEW, "Consulter les paiements"),
    (PERM_PAYMENT_INITIATE, "Initier un paiement"),
    (PERM_PAYMENT_CANCEL, "Annuler un paiement"),
    (PERM_PAYMENT_REFUND, "Rembourser un paiement"),
    (PERM_PAYMENT_MANAGE, "Administrer les paiements"),
    (PERM_PAYMENT_VIEW_STATS, "Voir les statistiques de paiement"),
)

# ------------------------------------------------------------------
# Permissions du module Tickets
# ------------------------------------------------------------------
PERM_TICKET_TYPE_CREATE = "ticket_type.create"
PERM_TICKET_TYPE_VIEW = "ticket_type.view"
PERM_TICKET_TYPE_UPDATE = "ticket_type.update"
PERM_TICKET_TYPE_DELETE = "ticket_type.delete"

PERM_TICKET_VIEW_OWN = "ticket.view_own"
PERM_TICKET_VIEW_EVENT = "ticket.view_event"
PERM_TICKET_ISSUE = "ticket.issue"
PERM_TICKET_CANCEL = "ticket.cancel"
PERM_TICKET_VIEW_ALL = "ticket.view_all"

ALL_TICKET_PERMISSIONS = (
    (PERM_TICKET_TYPE_CREATE, "Créer un type de ticket"),
    (PERM_TICKET_TYPE_VIEW, "Consulter un type de ticket"),
    (PERM_TICKET_TYPE_UPDATE, "Modifier un type de ticket"),
    (PERM_TICKET_TYPE_DELETE, "Supprimer/désactiver un type de ticket"),
    (PERM_TICKET_VIEW_OWN, "Voir ses propres tickets"),
    (PERM_TICKET_VIEW_EVENT, "Voir les tickets d'un événement"),
    (PERM_TICKET_ISSUE, "Émettre un ticket"),
    (PERM_TICKET_CANCEL, "Annuler un ticket"),
    (PERM_TICKET_VIEW_ALL, "Voir tous les tickets (admin)"),
)

# ------------------------------------------------------------------
# Permissions du module Certificates
# ------------------------------------------------------------------
PERM_CERTIFICATE_VIEW = "certificate.view"
PERM_CERTIFICATE_GENERATE = "certificate.generate"
PERM_CERTIFICATE_DOWNLOAD = "certificate.download"
PERM_CERTIFICATE_REVOKE = "certificate.revoke"
PERM_CERTIFICATE_VIEW_EVENT = "certificate.view_event"

ALL_CERTIFICATE_PERMISSIONS = (
    (PERM_CERTIFICATE_VIEW, "Voir ses certificats"),
    (PERM_CERTIFICATE_GENERATE, "Générer un certificat"),
    (PERM_CERTIFICATE_DOWNLOAD, "Télécharger un certificat"),
    (PERM_CERTIFICATE_REVOKE, "Révoquer un certificat"),
    (PERM_CERTIFICATE_VIEW_EVENT, "Voir les certificats d'un événement"),
)