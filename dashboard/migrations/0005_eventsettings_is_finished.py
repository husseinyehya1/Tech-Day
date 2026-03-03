from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_vipinvite_vip_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventsettings',
            name='is_finished',
            field=models.BooleanField(default=False, verbose_name='تم إنهاء الفعالية'),
        ),
    ]

