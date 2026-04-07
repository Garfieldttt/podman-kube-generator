from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0007_cookiebanner_en_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brand_name', models.CharField(default='Podman Kube Generator', max_length=100, verbose_name='Brand-Name (Navbar)')),
                ('brand_tagline', models.CharField(default='podman play kube · systemd quadlet', max_length=200, verbose_name='Brand-Tagline (Navbar)')),
                ('brand_icon', models.CharField(default='🦭', max_length=10, verbose_name='Brand-Icon (Emoji)')),
                ('home_heading', models.CharField(default='Podman Pod Generator', max_length=200, verbose_name='Homepage H1-Überschrift')),
                ('home_intro', models.TextField(default='Konfiguriere deinen Pod — bekomme fertiges Kubernetes YAML für podman play kube.', verbose_name='Homepage Intro-Text')),
                ('footer_author', models.CharField(default='', max_length=100, verbose_name='Footer: Autor-Name')),
                ('footer_author_url', models.URLField(default='', verbose_name='Footer: Autor-URL')),
                ('brand_name_en', models.CharField(blank=True, default='Podman Kube Generator', max_length=100, verbose_name='[EN] Brand-Name')),
                ('brand_tagline_en', models.CharField(blank=True, default='podman play kube · systemd quadlet', max_length=200, verbose_name='[EN] Brand-Tagline')),
                ('home_heading_en', models.CharField(blank=True, default='Podman Pod Generator', max_length=200, verbose_name='[EN] Homepage H1-Überschrift')),
                ('home_intro_en', models.TextField(blank=True, default='Configure your pod — get ready-to-use Kubernetes YAML for podman play kube.', verbose_name='[EN] Homepage Intro-Text')),
            ],
            options={
                'verbose_name': 'Website-Einstellungen',
                'verbose_name_plural': 'Website-Einstellungen',
            },
        ),
    ]
