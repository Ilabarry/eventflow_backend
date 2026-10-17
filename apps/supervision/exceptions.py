"""
Exceptions métier du module Supervision.

Elles héritent de BusinessException (common/exceptions/business.py) :
le handler global les convertit automatiquement au format standard
{success: false, message, errors}. Elles sont définies ICI, et non dans
le fichier partagé, pour ne modifier aucun fichier commun à l'équipe.

Deux familles :
    - erreurs « ordinaires » (404, 409) : rien de suspect ;
    - SecurityGuardDenied : un garde-fou de sécurité a bloqué l'action.
      Ces refus sont ENREGISTRÉS dans le journal d'audit (résultat DENIED).
"""

from rest_framework import status

from common.exceptions.business import BusinessException


# ==================================================================
# ERREURS ORDINAIRES
# ==================================================================
class SupervisionUserNotFound(BusinessException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Utilisateur introuvable."
    default_code = "supervision_user_not_found"


class UserAlreadySuspended(BusinessException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce compte est déjà suspendu."
    default_code = "user_already_suspended"


class UserAlreadyActive(BusinessException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce compte est déjà actif."
    default_code = "user_already_active"


# ==================================================================
# GARDE-FOUS DE SÉCURITÉ (refus journalisés)
# ==================================================================
class SecurityGuardDenied(BusinessException):
    """Base des refus de sécurité : toujours tracés dans l'audit."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Action refusée par une règle de sécurité."
    default_code = "security_guard_denied"


class ActorNoLongerAdmin(SecurityGuardDenied):
    """L'administrateur a perdu ses droits pendant la requête."""
    default_detail = "Votre compte n'a plus les droits d'administration."
    default_code = "actor_no_longer_admin"


class CannotChangeOwnStatus(SecurityGuardDenied):
    default_detail = "Vous ne pouvez pas suspendre ou réactiver votre propre compte."
    default_code = "cannot_change_own_status"


class AdminTargetRequiresSuperAdmin(SecurityGuardDenied):
    default_detail = (
        "Seul un super-administrateur peut suspendre ou réactiver "
        "un compte administrateur."
    )
    default_code = "admin_target_requires_super_admin"


class LastActiveAdmin(SecurityGuardDenied):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Action impossible : ce compte est le dernier administrateur actif."
    default_code = "last_active_admin"
