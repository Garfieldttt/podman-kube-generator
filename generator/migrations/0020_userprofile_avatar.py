from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0019_userstack_icon_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar',
            field=models.CharField(blank=True, max_length=200, verbose_name='Avatar', help_text='Lokaler Pfad (wird automatisch gesetzt beim Upload).'),
        ),
    ]
