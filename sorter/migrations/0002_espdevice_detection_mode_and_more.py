# Generated by Django 5.2 on 2025-05-16 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sorter', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='espdevice',
            name='detection_mode',
            field=models.CharField(choices=[('auto', 'Automatic'), ('manual', 'Manual'), ('hybrid', 'Hybrid')], default='manual', max_length=10),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='detection_sensitivity',
            field=models.IntegerField(default=70),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='green_threshold_max',
            field=models.IntegerField(default=70),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='green_threshold_min',
            field=models.IntegerField(default=31),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='ripe_threshold_max',
            field=models.IntegerField(default=30),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='ripe_threshold_min',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='use_webcam',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='espdevice',
            name='webcam_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
