from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0004_seosettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyticsSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True, verbose_name='Tracking aktiviert')),
                ('anonymize_ip', models.BooleanField(default=True, help_text='Nur erste 3 Oktette speichern, z.B. 192.168.1.x → 192.168.1.0 (DSGVO)', verbose_name='IP anonymisieren')),
                ('track_bots', models.BooleanField(default=False, verbose_name='Bots tracken')),
                ('retention_days', models.PositiveSmallIntegerField(default=90, help_text='Besuche nach X Tagen automatisch löschen. 0 = nie löschen.', verbose_name='Aufbewahrung (Tage)')),
            ],
            options={
                'verbose_name': 'Analytics-Einstellungen',
                'verbose_name_plural': 'Analytics-Einstellungen',
            },
        ),
        migrations.CreateModel(
            name='Visit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('path', models.CharField(max_length=500)),
                ('ip', models.CharField(blank=True, max_length=45, db_index=True)),
                ('country_code', models.CharField(blank=True, max_length=2)),
                ('country_name', models.CharField(blank=True, max_length=100)),
                ('browser_family', models.CharField(blank=True, max_length=80)),
                ('os_family', models.CharField(blank=True, max_length=80)),
                ('is_mobile', models.BooleanField(default=False)),
                ('referrer', models.CharField(blank=True, max_length=500)),
                ('session_key', models.CharField(blank=True, max_length=40)),
            ],
            options={
                'verbose_name': 'Besuch',
                'verbose_name_plural': 'Besuche',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='visit',
            index=models.Index(fields=['timestamp'], name='visit_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='visit',
            index=models.Index(fields=['country_code'], name='visit_cc_idx'),
        ),
        migrations.AddIndex(
            model_name='visit',
            index=models.Index(fields=['browser_family'], name='visit_br_idx'),
        ),
    ]
