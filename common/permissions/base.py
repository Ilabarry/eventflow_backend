"""
Permissions DRF transversales pour EVENTFLOW.

Ces permissions sont utilisées par toutes les apps (events, registrations,
payments, etc.) pour contrôler l'accès aux endpoints.

Rappel :
    - Authentification = "qui es-tu ?" (JWT)
    - Autorisation = "as-tu le droit ?" (permissions)
    - Rôle = un groupe de permissions (Participant, Organisateur, Admin)
    - Ownership = "es-tu propriétaire de cette ressource ?"
"""

from rest_framework.permissions import BasePermission

from apps.accounts.constants import (
    ROLE_ADMIN,
    ROLE_ORGANIZER,
    ROLE_PARTICIPANT,
)


# ==================================================================
# PERMISSION : Rôle spécifique
# ==================================================================
class IsParticipant(BasePermission):
    """
    Autorise uniquement les utilisateurs ayant le rôle 'participant'.
    
    Utilisation :
        class MyView(APIView):
            permission_classes = [IsAuthenticated, IsParticipant]
    """

    message = "Vous devez être participant pour accéder à cette ressource."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_role(ROLE_PARTICIPANT)
        )


class IsOrganizer(BasePermission):
    """
    Autorise uniquement les utilisateurs ayant le rôle 'organisateur'.
    
    Note : un admin est aussi autorisé (car il a tous les droits).
    """

    message = "Vous devez être organisateur pour accéder à cette ressource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.has_role(ROLE_ORGANIZER)
            or request.user.has_role(ROLE_ADMIN)
            or request.user.is_superuser
        )


class IsAdmin(BasePermission):
    """
    Autorise uniquement les utilisateurs ayant le rôle 'administrateur'
    ou le flag is_staff.
    """

    message = "Vous devez être administrateur pour accéder à cette ressource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.is_staff
            or request.user.is_superuser
            or request.user.has_role(ROLE_ADMIN)
        )


# ==================================================================
# PERMISSION : Permission granulaire
# ==================================================================
class HasPermission(BasePermission):
    """
    Vérifie que l'utilisateur possède une permission donnée (codename).

    Utilisation :
        class MyView(APIView):
            permission_classes = [IsAuthenticated, HasPermission]
            required_permission = 'event.create'

    Le champ 'required_permission' doit être défini sur la vue.
    """

    message = "Vous n'avez pas la permission requise pour cette action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Les superusers ont tous les droits
        if request.user.is_superuser or request.user.is_staff:
            return True

        codename = getattr(view, "required_permission", None)
        if not codename:
            # Si aucune permission n'est spécifiée, on refuse par défaut
            # (sécurité : mieux vaut refuser que d'ouvrir par erreur)
            return False

        return request.user.has_permission(codename)


def has_permission(codename: str):
    """
    Factory pour créer une classe de permission DRF liée à un codename.

    Utilisation :
        class MyView(APIView):
            permission_classes = [IsAuthenticated, has_permission('event.create')]

    Avantage : plus lisible que de définir 'required_permission' sur la vue.
    """

    class _HasSpecificPermission(BasePermission):
        message = f"Permission requise : {codename}"

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if request.user.is_superuser or request.user.is_staff:
                return True
            return request.user.has_permission(codename)

    return _HasSpecificPermission