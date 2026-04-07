from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0013_stacktemplate_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='stacktemplate',
            name='description_en',
            field=models.CharField(blank=True, default='', help_text='Short description (EN), e.g. "Self-hosted Git server with web UI"', max_length=160, verbose_name='Description (EN)'),
        ),
    ]
