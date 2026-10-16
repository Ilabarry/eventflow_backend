"""
Constantes et enums du module Attendance.

On utilise models.TextChoices (comme events et registrations) :
    - intégration native avec l'ORM et les migrations ;
    - valeurs en chaînes, faciles à sérialiser en JSON pour Angular ;
    - libellés lisibles dans l'admin.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==================================================================
# ENUM : Statut de présence
# ==================================================================
class AttendanceStatus(models.TextChoices):
    """
    Statut d'une fiche de présence.

    - PRESENT : le participant a été enregistré à l'entrée (check-in).
    - ABSENT  : l'organisateur a déclaré explicitement le participant absent
                (en général après l'événement).

    Il n'y a volontairement PAS de statut « NOT_CHECKED_IN » :
    un participant inscrit qui n'est pas encore arrivé n'a tout
    simplement AUCUNE fiche Attendance. Cela évite de créer des
    milliers de lignes vides à la publication d'un événement.
    """
    PRESENT = "PRESENT", _("Présent")
    ABSENT = "ABSENT", _("Absent")


# ==================================================================
# ENUM : Méthode de check-in
# ==================================================================
class CheckInMethod(models.TextChoices):
    """
    Méthode utilisée pour enregistrer la présence.

    Pour ajouter une méthode plus tard (MOBILE_APP, KIOSK, API, IMPORT),
    il suffit d'ajouter une ligne ici : la colonne est un simple texte,
    la migration générée ne modifiera pas les données existantes.
    """
    MANUAL = "MANUAL", _("Manuel")
    QR_CODE = "QR_CODE", _("QR Code")


# ==================================================================
# LONGUEURS DE CHAMPS
# ==================================================================
STATUS_MAX_LENGTH = 10
# 20 caractères laissent de la marge pour les méthodes futures.
CHECK_IN_METHOD_MAX_LENGTH = 20
