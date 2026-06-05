from django.db import connection, migrations


def reset_settings_id_sequence(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('settings', 'id'),
                COALESCE((SELECT MAX(id) FROM settings), 1)
            )
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("settings_app", "0002_user_ownership"),
    ]

    operations = [
        migrations.RunPython(reset_settings_id_sequence, migrations.RunPython.noop),
    ]
