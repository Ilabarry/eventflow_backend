"""
Services métier du module Attendance.

C'est ici, et uniquement ici, que l'on crée ou modifie une présence.
Les vues (phase 3) restent fines : elles appellent ces services.

⚠️ POINT CRITIQUE : la concurrence.
Deux scanners, un double clic ou un « retry » d'Angular peuvent envoyer
deux check-ins pour la même inscription à quelques millisecondes d'écart.

Stratégie (deux niveaux de protection) :
    1. Applicatif : transaction + SELECT ... FOR UPDATE sur l'inscription.
       La 2e requête ATTEND que la 1re ait fini, puis voit la présence
       déjà créée et répond 409 au lieu d'en créer une seconde.
    2. Base de données : le OneToOneField impose UNIQUE(registration_id).
       Si malgré tout deux INSERT arrivaient, PostgreSQL rejetterait le
       second (IntegrityError), que l'on convertit aussi en 409.

Idempotence : pas besoin de clé d'idempotence dédiée. L'état final est
le même quel que soit le nombre d'appels (une seule présence) ; les
appels répétés reçoivent simplement un 409 « déjà présent ».
"""

import logging
from django.db import transaction

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.attendance.constants import AttendanceStatus, CheckInMethod
from apps.attendance.models import Attendance
from apps.attendance.validators import (
    ensure_can_manage_event,
    validate_check_in_method,
    validate_event_for_absence,
    validate_event_for_check_in,
    validate_registration_for_attendance,
)
from apps.registrations.models import Registration
from common.exceptions.business import (
    AlreadyCheckedIn,
    AttendanceRegistrationNotFound,
     InvalidQRCode,
)

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service métier pour les présences."""

    # ------------------------------------------------------------------
    # OUTIL INTERNE : charger et verrouiller l'inscription
    # ------------------------------------------------------------------
    @staticmethod
    def _lock_registration(registration_id) -> Registration:
        """
        Charge l'inscription ET verrouille sa ligne jusqu'à la fin
        de la transaction en cours.

        Pourquoi verrouiller l'inscription (et pas l'événement) ?
            - C'est la ressource disputée : un check-in concerne UNE
              inscription. Les check-ins des autres participants du même
              événement ne sont pas bloqués.
            - Cela empêche aussi une annulation simultanée de l'inscription
              pendant que l'on enregistre la présence.

        of=("self",) : on ne verrouille que la ligne de l'inscription,
        pas celle de l'événement chargé par select_related.
        """
        registration = (
            Registration.objects
            .select_for_update(of=("self",))
            .select_related("event")
            .filter(pk=registration_id)
            .first()
        )
        if registration is None:
            raise AttendanceRegistrationNotFound()
        return registration

    # ------------------------------------------------------------------
    # CHECK-IN
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def check_in(
        *,
        registration_id,
        performed_by,
        method: str = CheckInMethod.MANUAL,
    ) -> Attendance:
        """
        Enregistre la présence d'un participant.

        Args:
            registration_id: UUID de l'inscription (seule donnée venant
                du frontend ; l'événement en est déduit côté serveur).
            performed_by: l'utilisateur qui fait le check-in (request.user).
            method: méthode utilisée (MANUAL par défaut).

        Returns:
            La fiche Attendance au statut PRESENT.

        Raises:
            AttendanceRegistrationNotFound (404), UnauthorizedEventAccess (403),
            RegistrationNotEligibleForCheckIn (400), EventNotPublished /
            EventCancelled / EventCompleted / CheckInNotOpen (400),
            AlreadyCheckedIn (409).
        """
        validate_check_in_method(method)

        # 1. Verrouiller l'inscription (voir _lock_registration)
        registration = AttendanceService._lock_registration(registration_id)
        event = registration.event

        # 2. Vérifier l'autorisation AVANT toute autre information :
        #    un organisateur étranger ne doit rien apprendre de l'inscription.
        ensure_can_manage_event(performed_by, event)

        # 3. Vérifier l'inscription et l'événement
        validate_registration_for_attendance(registration)
        validate_event_for_check_in(event)

        now = timezone.now()
        existing = Attendance.objects.filter(registration=registration).first()

        # 4a. Déjà présent : refus explicite (409)
        if existing and existing.is_present:
            logger.info(
                "Check-in refused (already present) | registration=%s | by=%s",
                registration.id, performed_by.id,
            )
            raise AlreadyCheckedIn(
                detail="Ce participant est déjà enregistré comme présent "
                       f"(depuis {timezone.localtime(existing.checked_in_at):%H:%M})."
            )

        # 4b. Déclaré absent puis arrivé en retard : on corrige la fiche
        if existing:
            existing.status = AttendanceStatus.PRESENT
            existing.checked_in_at = now
            existing.check_in_method = method
            existing.recorded_by = performed_by
            existing.save(update_fields=[
                "status", "checked_in_at", "check_in_method",
                "recorded_by", "updated_at",
            ])
            logger.info(
                "Check-in (absent → present) | registration=%s | method=%s | by=%s",
                registration.id, method, performed_by.id,
            )
            return existing

        # 4c. Première présence : création
        try:
            # Point de sauvegarde : si PostgreSQL rejette l'INSERT, seule
            # cette étape est annulée et l'on peut répondre proprement.
            with transaction.atomic():
                attendance = Attendance.objects.create(
                    registration=registration,
                    status=AttendanceStatus.PRESENT,
                    checked_in_at=now,
                    check_in_method=method,
                    recorded_by=performed_by,
                )
        except IntegrityError:
            # Filet de sécurité : la contrainte UNIQUE a bloqué un doublon.
            logger.warning(
                "Check-in IntegrityError (duplicate) | registration=%s",
                registration.id,
            )
            raise AlreadyCheckedIn()

        logger.info(
            "Check-in success | registration=%s | event=%s | method=%s | by=%s",
            registration.id, event.id, method, performed_by.id,
        )

        # ⚠️ NOUVEAU : notifier le participant
        try:
            with transaction.atomic():
                from apps.notifications.constants import NotificationType
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    user=registration.participant,
                    title="Participation enregistrée",
                    message=(
                        f"Votre présence à « {registration.event.title} » "
                        f"a bien été enregistrée."
                    ),
                    notification_type=NotificationType.ATTENDANCE,
                    related_entity_type="attendance",
                    related_entity_id=str(attendance.id),
                    metadata={"url": f"/participant/presences/{attendance.id}"},
                )
        except Exception as e:
            logger.warning("Notification failed on check-in | err=%s", e)

        return attendance

    # ------------------------------------------------------------------
    # ABSENCE
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def mark_absent(*, registration_id, performed_by) -> Attendance:
        """
        Déclare un participant absent (après le début de l'événement).

        - Si le participant est déjà PRESENT : refus (409). On ne
          transforme pas une présence réelle en absence.
        - Si une fiche ABSENT existe déjà : on la renvoie telle quelle
          (appel idempotent).

        Raises:
            AttendanceRegistrationNotFound (404), UnauthorizedEventAccess (403),
            RegistrationNotEligibleForCheckIn (400), EventNotPublished /
            EventCancelled / CheckInNotOpen (400), AlreadyCheckedIn (409).
        """
        registration = AttendanceService._lock_registration(registration_id)
        event = registration.event

        ensure_can_manage_event(performed_by, event)
        validate_registration_for_attendance(registration)
        validate_event_for_absence(event)

        existing = Attendance.objects.filter(registration=registration).first()
        if existing and existing.is_present:
            raise AlreadyCheckedIn(
                detail="Ce participant est enregistré comme présent : "
                       "il ne peut pas être déclaré absent."
            )
        if existing:
            return existing

        try:
            with transaction.atomic():
                attendance = Attendance.objects.create(
                    registration=registration,
                    status=AttendanceStatus.ABSENT,
                    recorded_by=performed_by,
                )
        except IntegrityError:
            # Une autre requête a créé la fiche entre-temps : on la renvoie.
            return Attendance.objects.get(registration=registration)

        logger.info(
            "Marked absent | registration=%s | event=%s | by=%s",
            registration.id, event.id, performed_by.id,
        )
        return attendance


    # ------------------------------------------------------------------
    # CHECK-IN PAR QR CODE
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def check_in_by_qr(*, qr_code: str, performed_by) -> Attendance:
        """
        Enregistre la présence via un QR code scanné.

        Sécurité :
            - Vérifie la signature HMAC du QR (résiste à la falsification).
            - Vérifie que le ticket existe et est VALID.
            - Vérifie que le ticket appartient au bon événement.
            - Marque le ticket comme USED (via TicketService.mark_as_used).
            - Crée la présence (réutilise check_in()).

        Args:
            qr_code: le payload brut scanné (format: reference|signature).
            performed_by: l'utilisateur qui fait le check-in.

        Raises:
            BusinessException(400): si le QR est invalide ou falsifié.
            TicketNotUsable(409): si le ticket est déjà USED, EXPIRED ou CANCELLED.
            AlreadyCheckedIn(409): si la présence existe déjà.
            UnauthorizedEventAccess(403): si l'organisateur n'est pas le bon.
        """
        from apps.tickets.services import TicketService
        from apps.tickets.constants import TicketStatus
        from common.exceptions.business import BusinessException, TicketNotUsable

        # 1. Vérifier la signature du QR
        ticket = TicketService.verify_qr_payload(qr_code)
        if ticket is None:
            raise InvalidQRCode()

        # 2. Vérifier que le ticket est VALID
        if ticket.status != TicketStatus.VALID:
            raise TicketNotUsable(
                detail=f"Ce ticket n'est pas utilisable (statut: {ticket.status})."
            )

        # 3. Vérifier que le ticket appartient au bon événement
        if ticket.registration.event_id != ticket.registration.event_id:
            raise BusinessException(
                detail="Le ticket n'appartient pas à cet événement.",
                status_code=400,
            )

        # 4. Vérifier l'autorisation de l'organisateur
        ensure_can_manage_event(performed_by, ticket.registration.event)

        # 5. Faire le check-in (réutilise la logique existante)
        attendance = AttendanceService.check_in(
            registration_id=ticket.registration.id,
            performed_by=performed_by,
            method=CheckInMethod.QR_CODE,
        )

        # 6. Marquer le ticket comme USED
        TicketService.mark_as_used(ticket=ticket)

        logger.info(
            "QR check-in success | ticket=%s | registration=%s | by=%s",
            ticket.reference, ticket.registration.id, performed_by.id,
        )

        return attendance