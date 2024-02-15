# Generated by Django 3.2.18 on 2023-05-23 07:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loc_insurancemaps', '0002_volume_mosaic_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='volume',
            name='mosaic_preference',
            field=models.CharField(choices=[('mosaicjson', 'MosaicJSON'), ('geotiff', 'GeoTIFF')], default='mosaicjson', max_length=20),
        ),
    ]