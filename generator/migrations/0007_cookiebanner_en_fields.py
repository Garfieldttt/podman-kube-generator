from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0006_cookiebannersettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='cookiebannersettings',
            name='title_en',
            field=models.CharField(blank=True, default='Cookies & Privacy', max_length=200, verbose_name='[EN] Titel'),
        ),
        migrations.AddField(
            model_name='cookiebannersettings',
            name='text_en',
            field=models.TextField(blank=True, default='This website uses cookies for analytics. By clicking "Accept all" you agree to this.', verbose_name='[EN] Beschreibungstext'),
        ),
        migrations.AddField(
            model_name='cookiebannersettings',
            name='accept_label_en',
            field=models.CharField(blank=True, default='Accept all', max_length=80, verbose_name='[EN] Button: Alle akzeptieren'),
        ),
        migrations.AddField(
            model_name='cookiebannersettings',
            name='decline_label_en',
            field=models.CharField(blank=True, default='Essential only', max_length=80, verbose_name='[EN] Button: Ablehnen'),
        ),
        migrations.AddField(
            model_name='cookiebannersettings',
            name='privacy_label_en',
            field=models.CharField(blank=True, default='Privacy Policy', max_length=80, verbose_name='[EN] Datenschutz Link-Text'),
        ),
        migrations.AddField(
            model_name='cookiebannersettings',
            name='analytics_label_en',
            field=models.CharField(blank=True, default='Analytics', max_length=80, verbose_name='[EN] Kategorie: Analyse — Bezeichnung'),
        ),
        migrations.AddField(
            model_name='cookiebannersettings',
            name='analytics_description_en',
            field=models.TextField(blank=True, default='Helps us understand how visitors use the site (anonymised, no cross-site tracking).', verbose_name='[EN] Kategorie: Analyse — Beschreibung'),
        ),
    ]
