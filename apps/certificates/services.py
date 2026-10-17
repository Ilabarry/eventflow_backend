"""
Services métier du module Certificates.

⚠️ POINTS CRITIQUES :
    1. L'éligibilité est vérifiée AVANT toute génération.
    2. La génération est transactionnelle (PDF + Certificate ensemble).
    3. Un seul certificat actif par Registration (OneToOne + service).
    4. La référence et le verification_code sont uniques.
"""

import logging
import secrets

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.certificates.constants import (
    REFERENCE_ALPHABET,
    REFERENCE_PREFIX,
    REFERENCE_SUFFIX_LENGTH,
    VERIFICATION_CODE_BYTES,
    CertificateStatus,
)
from apps.certificates.models import Certificate
from apps.certificates.pdf import generate_certificate_pdf
from apps.certificates.validators import (
    validate_attendance_for_certificate,
    validate_event_for_certificate,
    validate_no_existing_certificate,
    validate_registration_for_certificate,
)
from apps.registrations.models import Registration
from common.exceptions.business import (
    CertificateAlreadyRevoked,
    CertificateGenerationError,
    CertificateNotFound,
    InvalidCertificateState,
)

logger = logging.getLogger(__name__)


class CertificateService:
    """Service métier pour les certificats."""

    # ------------------------------------------------------------------
    # GÉNÉRATION DE RÉFÉRENCE
    # ------------------------------------------------------------------
    @staticmethod
    def generate_reference() -> str:
        """Génère une référence unique CERT-YYYY-XXXXXX."""
        year = timezone.now().year
        suffix = "".join(
            secrets.choice(REFERENCE_ALPHABET)
            for _ in range(REFERENCE_SUFFIX_LENGTH)
        )
        return f"{REFERENCE_PREFIX}-{year}-{suffix}"

    @staticmethod
    def generate_verification_code() -> str:
        """Génère un code de vérification hexadécimal unique."""
        return secrets.token_hex(VERIFICATION_CODE_BYTES)

    @staticmethod
    def _generate_unique_reference() -> str:
        """Génère une référence unique avec retry."""
        for _ in range(10):
            ref = CertificateService.generate_reference()
            if not Certificate.objects.filter(reference=ref).exists():
                return ref
        raise RuntimeError("Impossible de générer une référence unique.")

    @staticmethod
    def _generate_unique_verification_code() -> str:
        """Génère un verification_code unique avec retry."""
        for _ in range(10):
            code = CertificateService.generate_verification_code()
            if not Certificate.objects.filter(verification_code=code).exists():
                return code
        raise RuntimeError("Impossible de générer un verification_code unique.")

    # ------------------------------------------------------------------
    # ÉLIGIBILITÉ
    # ------------------------------------------------------------------
    @staticmethod
    def check_eligibility(registration: Registration) -> dict:
        """
        Vérifie si une inscription est éligible à un certificat.

        Returns:
            dict avec eligible (bool) et reason (str) si non éligible.
        """
        try:
            validate_registration_for_certificate(registration)
            validate_event_for_certificate(registration.event)
            validate_attendance_for_certificate(registration)
            validate_no_existing_certificate(registration)
            return {"eligible": True, "reason": None}
        except Exception as e:
            return {"eligible": False, "reason": str(e.detail) if hasattr(e, "detail") else str(e)}

    # ------------------------------------------------------------------
    # GÉNÉRATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def generate_certificate(registration: Registration) -> Certificate:
        """
        Génère un certificat pour une inscription éligible.

        Étapes :
            1. Vérifier l'éligibilité.
            2. Créer le Certificate (PENDING) avec reference + verification_code.
            3. Générer le PDF.
            4. Sauvegarder le PDF.
            5. Passer à ISSUED.
            6. Retourner le Certificate.

        Raises:
            CertificateNotEligible: Si l'inscription n'est pas éligible.
            AttendanceRequired: Si le participant n'est pas PRESENT.
            EventNotEnded: Si l'événement n'est pas terminé.
            CertificateAlreadyExists: Si un certificat actif existe déjà.
            CertificateGenerationError: Si le PDF échoue.
        """
        # 1. Éligibilité
        validate_registration_for_certificate(registration)
        validate_event_for_certificate(registration.event)
        validate_attendance_for_certificate(registration)
        validate_no_existing_certificate(registration)

        # 2. Créer le Certificate (PENDING)
        try:
            certificate = Certificate.objects.create(
                registration=registration,
                reference=CertificateService._generate_unique_reference(),
                verification_code=CertificateService._generate_unique_verification_code(),
                status=CertificateStatus.PENDING,
            )
        except IntegrityError:
            logger.warning(
                "Certificate IntegrityError (race condition) | registration=%s",
                registration.id,
            )
            from common.exceptions.business import CertificateAlreadyExists
            raise CertificateAlreadyExists()

        # 3. Générer le PDF
        try:
            pdf_bytes = generate_certificate_pdf(certificate)
        except Exception as e:
            logger.exception(
                "PDF generation failed | certificate=%s | err=%s",
                certificate.reference, e,
            )
            raise CertificateGenerationError(
                detail="Erreur lors de la génération du PDF. Réessayez plus tard."
            )

        # 4. Sauvegarder le PDF
        try:
            filename = f"{certificate.reference}.pdf"
            certificate.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
        except Exception as e:
            logger.exception(
                "PDF save failed | certificate=%s | err=%s",
                certificate.reference, e,
            )
            raise CertificateGenerationError()

        # 5. Passer à ISSUED
        certificate.status = CertificateStatus.ISSUED
        certificate.save(update_fields=["status", "pdf_file", "updated_at"])

        logger.info(
            "Certificate issued | ref=%s | registration=%s",
            certificate.reference, registration.reference,
        )

        return certificate

    # ------------------------------------------------------------------
    # RÉVOCATION
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def revoke_certificate(*, certificate: Certificate, revoked_by) -> Certificate:
        """Révoque un certificat."""
        if certificate.status == CertificateStatus.REVOKED:
            raise CertificateAlreadyRevoked()

        if not certificate.can_transition_to(CertificateStatus.REVOKED):
            raise InvalidCertificateState(
                detail=f"Transition '{certificate.status}' → 'REVOKED' non autorisée."
            )

        certificate.status = CertificateStatus.REVOKED
        certificate.revoked_at = timezone.now()
        certificate.revoked_by = revoked_by
        certificate.save(update_fields=["status", "revoked_at", "revoked_by", "updated_at"])

        logger.info(
            "Certificate revoked | ref=%s | by=%s",
            certificate.reference, revoked_by.id if revoked_by else "system",
        )
        return certificate

    # ------------------------------------------------------------------
    # VÉRIFICATION PUBLIQUE
    # ------------------------------------------------------------------
    @staticmethod
    def verify_certificate(verification_code: str) -> Certificate:
        """
        Vérifie un certificat à partir de son verification_code.

        Raises:
            CertificateNotFound: Si le code est invalide ou inexistant.
        """
        certificate = (
            Certificate.objects
            .select_related(
                "registration",
                "registration__participant",
                "registration__event",
            )
            .filter(verification_code=verification_code)
            .first()
        )
        if certificate is None:
            raise CertificateNotFound()
        return certificate