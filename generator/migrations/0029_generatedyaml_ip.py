from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0028_generatedyaml'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedyaml',
            name='ip',
            field=models.CharField(blank=True, default='', max_length=45),
        ),
    ]
