from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0011_sitesettings_donation_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='FooterLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=80, verbose_name='Bezeichnung')),
                ('url', models.URLField(verbose_name='URL')),
                ('icon', models.CharField(default='bi-link-45deg', help_text='z.B. bi-github, bi-house, bi-globe2', max_length=60, verbose_name='Bootstrap Icon Klasse')),
                ('sort_order', models.PositiveSmallIntegerField(default=0, verbose_name='Reihenfolge')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('open_new_tab', models.BooleanField(default=True, verbose_name='Neuer Tab')),
            ],
            options={
                'verbose_name': 'Footer-Link',
                'verbose_name_plural': 'Footer-Links',
                'ordering': ['sort_order', 'pk'],
            },
        ),
    ]
