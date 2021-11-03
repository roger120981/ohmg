# Generated by Django 2.2.20 on 2021-11-03 18:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0031_auto_20201107_2241'),
        ('loc_insurancemaps', '0002_auto_20211021_1410'),
    ]

    operations = [
        migrations.AddField(
            model_name='volume',
            name='status',
            field=models.CharField(choices=[('not started', 'not started'), ('initializing...', 'initializing...'), ('started', 'started'), ('all georeferenced', 'all georeferenced')], default='not started', max_length=50),
        ),
        migrations.CreateModel(
            name='FullThumbnail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='full_thumbs')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.Document')),
            ],
        ),
    ]
