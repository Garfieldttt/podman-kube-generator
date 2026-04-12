"""
Management Command: python manage.py load_stacks

Imports all stack templates from generator/fixtures/stack_templates.json.
Existing entries (same key) are updated, new ones are created.
Manually created DB entries without a matching key are preserved.
"""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from generator.models import StackTemplate


FIXTURE_PATH = Path(__file__).resolve().parents[2] / 'fixtures' / 'stack_templates.json'


class Command(BaseCommand):
    help = 'Import/update stack templates from fixtures/stack_templates.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite all fields including manually edited stack_data (default: update_or_create)',
        )

    def handle(self, *args, **options):
        if not FIXTURE_PATH.exists():
            self.stderr.write(self.style.ERROR(f'Fixture not found: {FIXTURE_PATH}'))
            return

        with open(FIXTURE_PATH, encoding='utf-8') as f:
            data = json.load(f)

        created_count = 0
        updated_count = 0

        for i, entry in enumerate(data):
            fields = entry['fields']
            key = fields['key']

            defaults = {
                'label': fields['label'],
                'icon': fields.get('icon', 'bi-collection'),
                'category': fields.get('category', 'Other'),
                'description': fields.get('description', ''),
                'stack_data': fields['stack_data'],
                'is_active': fields.get('is_active', True),
                'sort_order': fields.get('sort_order', i),
            }

            obj, created = StackTemplate.objects.update_or_create(
                key=key,
                defaults=defaults,
            )
            if created:
                created_count += 1
                self.stdout.write(f'  + {key} ({fields["label"]})')
            else:
                updated_count += 1
                self.stdout.write(f'  ~ {key} ({fields["label"]})')

        self.stdout.write(self.style.SUCCESS(
            f'Done: {created_count} created, {updated_count} updated.'
        ))
