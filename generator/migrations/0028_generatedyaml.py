from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0027_analytics_exclude_blocked'),
    ]

    operations = [
        migrations.CreateModel(
            name='GeneratedYAML',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('mode', models.CharField(default='rootless', max_length=10)),
                ('container_count', models.PositiveSmallIntegerField(default=1)),
                ('init_count', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Generated YAML',
                'verbose_name_plural': 'Generated YAMLs',
                'ordering': ['-timestamp'],
            },
        ),
    ]
