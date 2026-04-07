from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0029_generatedyaml_ip'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='compose_import_timeout',
            field=models.PositiveSmallIntegerField(
                default=10,
                help_text='Maximale Verarbeitungszeit für einen Compose-Import. 0 = kein Limit.',
                verbose_name='Compose Import Timeout (Sekunden)',
            ),
        ),
    ]
