from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Löscht das TOTP-Gerät eines Users (Notfall-Reset)'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Benutzername')

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" nicht gefunden.')

        try:
            device = user.totp_device
            device.delete()
            self.stdout.write(self.style.SUCCESS(
                f'TOTP für "{username}" gelöscht. '
                f'Beim nächsten Admin-Login wird TOTP neu eingerichtet.'
            ))
        except Exception:
            self.stdout.write(self.style.WARNING(
                f'Kein TOTP-Gerät für "{username}" gefunden.'
            ))
