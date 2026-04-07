from django.db import migrations, models


INITIAL_MESSAGES = [
    ('Kubernetes YAML für podman play kube - fertig in Sekunden.', 'Kubernetes YAML for podman play kube - ready in seconds.'),
    ('Kein Docker, kein Problem - Podman ist rootless by default.', 'No Docker, no problem - Podman is rootless by default.'),
    ('Definiere deinen Pod, klick auf Generate, fertig.', 'Define your pod, click Generate, done.'),
    ('Unterstützt Init-Container, Volumes und Port-Mappings.', 'Supports init containers, volumes and port mappings.'),
    ('Rootless Podman - deine Container laufen ohne Root-Rechte.', 'Rootless Podman - your containers run without root privileges.'),
    ('podman play kube: vom YAML zum laufenden Pod in einem Befehl.', 'podman play kube: from YAML to running pod in one command.'),
    ('Speichere deine Konfiguration und teile den Link.', 'Save your configuration and share the link.'),
    ('Multi-Container-Stacks leicht gemacht - alles in einem Pod.', 'Multi-container stacks made easy - everything in one pod.'),
    ('Systemd Quadlet - der moderne Weg für Container als Services.', 'Systemd Quadlet - the modern way for containers as services.'),
    ('Host-Netzwerk, DNS, Hostname - alles konfigurierbar.', 'Host network, DNS, hostname - all configurable.'),
    ('Vorgefertigte Stacks für WordPress, Nextcloud, Gitea und mehr.', 'Pre-built stacks for WordPress, Nextcloud, Gitea and more.'),
    ('Umgebungsvariablen, Resource-Limits, Security-Optionen - alles dabei.', 'Environment variables, resource limits, security options - all included.'),
    ('Portiere deine docker-compose.yml zu Kubernetes YAML.', 'Migrate your docker-compose.yml to Kubernetes YAML.'),
    ('Podman 4.0+ unterstützt podman play kube nativ.', 'Podman 4.0+ supports podman play kube natively.'),
    ('Kein Kubernetes-Cluster nötig - podman play kube reicht.', 'No Kubernetes cluster needed - podman play kube is enough.'),
    ('Volumes werden automatisch als PersistentVolumeClaim angelegt.', 'Volumes are automatically created as PersistentVolumeClaim.'),
    ('User-Namespace Remapping schützt deinen Host.', 'User namespace remapping protects your host.'),
    ('Restart-Policy: always, on-failure oder never - du entscheidest.', 'Restart policy: always, on-failure or never - you decide.'),
    ('Generiertes YAML direkt als Systemd-Service verwendbar.', 'Generated YAML directly usable as a systemd service.'),
    ('IPC, PID und Netzwerk-Namespace - volle Kontrolle über Isolation.', 'IPC, PID and network namespace - full control over isolation.'),
    ('Container-Images direkt aus Docker Hub, GHCR oder Quay.io.', 'Container images directly from Docker Hub, GHCR or Quay.io.'),
    ('Hiro hilft dir, den perfekten Pod zu konfigurieren.', 'Hiro helps you configure the perfect pod.'),
    ('Open Source - kein Account, kein Tracking, keine Limits.', 'Open source - no account, no tracking, no limits.'),
    ('Podman - die daemonlose Container-Engine für Linux.', 'Podman - the daemonless container engine for Linux.'),
]


def load_initial_messages(apps, schema_editor):
    HiroMessage = apps.get_model('generator', 'HiroMessage')
    for i, (text_de, text_en) in enumerate(INITIAL_MESSAGES):
        HiroMessage.objects.create(
            text_de=text_de,
            text_en=text_en,
            is_active=True,
            sort_order=i,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0008_sitesettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='HiroMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text_de', models.CharField(max_length=300, verbose_name='Text (Deutsch)')),
                ('text_en', models.CharField(max_length=300, verbose_name='Text (English)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('sort_order', models.PositiveSmallIntegerField(default=0, verbose_name='Reihenfolge')),
            ],
            options={
                'verbose_name': 'Hiro-Nachricht',
                'verbose_name_plural': 'Hiro-Nachrichten',
                'ordering': ['sort_order', 'pk'],
            },
        ),
        migrations.RunPython(load_initial_messages, migrations.RunPython.noop),
    ]
