from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0005_visit_analyticssettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='CookieBannerSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True, verbose_name='Banner aktiviert')),
                ('position', models.CharField(choices=[('bottom', 'Unten (Bar)'), ('top', 'Oben (Bar)'), ('modal', 'Mitte (Modal)')], default='bottom', max_length=10, verbose_name='Position')),
                ('title', models.CharField(default='Cookies & Datenschutz', max_length=200, verbose_name='Titel')),
                ('text', models.TextField(default='Diese Website verwendet Cookies für Analyse-Zwecke. Mit Klick auf „Alle akzeptieren" stimmst du dem zu.', verbose_name='Beschreibungstext')),
                ('accept_label', models.CharField(default='Alle akzeptieren', max_length=80, verbose_name='Button: Alle akzeptieren')),
                ('decline_label', models.CharField(default='Nur notwendige', max_length=80, verbose_name='Button: Ablehnen')),
                ('show_decline_button', models.BooleanField(default=True, verbose_name='Ablehnen-Button anzeigen')),
                ('privacy_url', models.URLField(blank=True, verbose_name='Datenschutz-URL')),
                ('privacy_label', models.CharField(default='Datenschutzerklärung', max_length=80, verbose_name='Datenschutz Link-Text')),
                ('analytics_label', models.CharField(default='Analyse', max_length=80, verbose_name='Kategorie: Analyse — Bezeichnung')),
                ('analytics_description', models.TextField(default='Hilft uns zu verstehen, wie Besucher die Seite nutzen (anonymisiert, kein Tracking über Seiten hinweg).', verbose_name='Kategorie: Analyse — Beschreibung')),
                ('lifetime_days', models.PositiveSmallIntegerField(default=365, verbose_name='Cookie-Lebensdauer (Tage)')),
            ],
            options={
                'verbose_name': 'Cookie-Banner',
                'verbose_name_plural': 'Cookie-Banner',
            },
        ),
    ]
