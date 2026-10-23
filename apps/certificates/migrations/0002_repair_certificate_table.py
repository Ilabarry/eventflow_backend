
from django.db import migrations


def repair_certificate_table(apps, schema_editor):
    """
    Reconstruit la table Certificate si elle ne contient
    que les anciennes colonnes de base.
    """
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'certificates_certificate'
              AND table_schema = current_schema()
        """)
        columns = {row[0] for row in cursor.fetchall()}

    required_columns = {
        "id",
        "reference",
        "verification_code",
        "status",
        "pdf_file",
        "issued_at",
        "revoked_at",
        "created_at",
        "updated_at",
        "registration_id",
        "revoked_by_id",
    }

    # Ne pas modifier automatiquement une table dont la structure
    # est différente de celle que nous avons vérifiée.
    if columns == {"id", "reference", "issued_at", "pdf_file", "created_at"}:
        Certificate = apps.get_model("certificates", "Certificate")

        # La table a été vérifiée vide avant cette réparation.
        schema_editor.delete_model(Certificate)
        schema_editor.create_model(Certificate)

    elif columns != required_columns:
        raise RuntimeError(
            "Structure inattendue de certificates_certificate. "
            "Aucune modification automatique n'a été effectuée."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("certificates", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            repair_certificate_table,
            migrations.RunPython.noop,
        ),
    ]
