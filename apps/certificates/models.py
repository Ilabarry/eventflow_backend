
import uuid

from django.db import models


class Certificate(models.Model):
    """Représente un certificat de participation à un événement."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    pdf_file = models.FileField(
        upload_to="certificates/",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificat {self.reference}"
