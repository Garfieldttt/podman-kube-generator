from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0012_footerlink'),
    ]

    operations = [
        migrations.AddField(
            model_name='stacktemplate',
            name='description',
            field=models.CharField(blank=True, default='', help_text='Kurzbeschreibung (DE), z.B. "Self-hosted Git-Server mit Web-UI"', max_length=160),
        ),
        migrations.AddField(
            model_name='stacktemplate',
            name='description_en',
            field=models.CharField(blank=True, default='', help_text='Short description (EN), e.g. "Self-hosted Git server with web UI"', max_length=160, verbose_name='Description (EN)'),
        ),
    ]
