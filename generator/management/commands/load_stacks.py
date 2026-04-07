"""
Management Command: python manage.py load_stacks

Importiert alle Stacks aus stacks.py in die StackTemplate-Tabelle.
Bereits vorhandene Einträge (gleicher key) werden aktualisiert (update_or_create).
Neue Stacks in stacks.py werden hinzugefügt, manuell angelegte DB-Einträge bleiben erhalten.
"""
from django.core.management.base import BaseCommand
from generator.models import StackTemplate
from generator.stacks import STACKS


class Command(BaseCommand):
    help = 'Importiert/aktualisiert Stacks aus stacks.py in die Datenbank'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Überschreibt auch manuell geänderte stack_data (default: nur neue Felder aktualisieren)',
        )

    def handle(self, *args, **options):
        skip_keys = {'label', 'icon', 'category', 'description', 'description_en'}  # description_en kept for backwards compat
        created_count = 0
        updated_count = 0

        for i, (key, stack) in enumerate(STACKS.items()):
            stack_data = {k: v for k, v in stack.items() if k not in skip_keys}

            defaults = {
                'label': stack['label'],
                'icon': stack.get('icon', 'bi-collection'),
                'category': stack.get('category', 'Sonstige'),
                'stack_data': stack_data,
                'sort_order': i,
            }
            # Use description_en if available (English-only), fall back to description
            if 'description_en' in stack:
                defaults['description'] = stack['description_en']
            elif 'description' in stack:
                defaults['description'] = stack['description']

            obj, created = StackTemplate.objects.update_or_create(
                key=key,
                defaults=defaults,
            )
            if created:
                created_count += 1
                self.stdout.write(f'  + {key} ({stack["label"]})')
            else:
                updated_count += 1
                self.stdout.write(f'  ~ {key} ({stack["label"]})')

        self.stdout.write(self.style.SUCCESS(
            f'Fertig: {created_count} neu angelegt, {updated_count} aktualisiert.'
        ))
