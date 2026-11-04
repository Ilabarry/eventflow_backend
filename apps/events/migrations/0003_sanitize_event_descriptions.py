"""
Nettoie les descriptions d'événements déjà stockées.

Les anciennes données peuvent contenir du HTML dangereux (XSS stockée)
saisi avant l'ajout du nettoyage à l'écriture. Cette migration applique
la même liste blanche bleached aux descriptions existantes.
"""

from django.db import migrations

from common.utils.sanitize import sanitize_rich_text


def sanitize_event_descriptions(apps, schema_editor):
    Event = apps.get_model("events", "Event")

    for event in Event.objects.exclude(description="").iterator(chunk_size=200):
        cleaned = sanitize_rich_text(event.description)
        if cleaned != event.description:
            Event.objects.filter(pk=event.pk).update(description=cleaned)


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_event_base_price_event_event_price_consistent"),
    ]

    operations = [
        migrations.RunPython(
            sanitize_event_descriptions,
            migrations.RunPython.noop,
        ),
    ]
