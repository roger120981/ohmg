# Generated by Django 3.2.18 on 2023-04-04 19:44

from django.conf import settings
import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import ohmg.georeference.models.resources
import ohmg.georeference.storage
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='GCPGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('crs_epsg', models.IntegerField(blank=True, null=True)),
                ('transformation', models.CharField(blank=True, choices=[('tps', 'tps'), ('poly1', 'poly1'), ('poly2', 'poly2'), ('poly3', 'poly3')], max_length=20, null=True)),
            ],
            options={
                'verbose_name': 'GCP Group',
                'verbose_name_plural': 'GCP Groups',
            },
        ),
        migrations.CreateModel(
            name='SessionBase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(blank=True, choices=[('p', 'Preparation'), ('g', 'Georeference')], max_length=1)),
                ('stage', models.CharField(choices=[('input', 'input'), ('processing', 'processing'), ('finished', 'finished')], default='input', max_length=11)),
                ('status', models.CharField(default='getting user input', max_length=50)),
                ('data', models.JSONField(blank=True, default=dict)),
                ('user_input_duration', models.IntegerField(blank=True, null=True)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('date_modified', models.DateTimeField(default=django.utils.timezone.now)),
                ('date_run', models.DateTimeField(blank=True, null=True)),
                ('note', models.CharField(blank=True, max_length=255, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ItemBase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='title')),
                ('slug', models.CharField(blank=True, max_length=128, null=True)),
                ('type', models.CharField(choices=[('document', 'Document'), ('layer', 'Layer')], max_length=10)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('attribution', models.CharField(blank=True, max_length=2048, null=True)),
                ('status', models.CharField(blank=True, choices=[('unprepared', 'Unprepared'), ('needs review', 'Needs Review'), ('splitting', 'Splitting - in progress'), ('split', 'Split'), ('prepared', 'Prepared'), ('georeferencing', 'Georeferencing - in progress'), ('georeferenced', 'Georeferenced')], default='unprepared', max_length=50, null=True)),
                ('x0', models.DecimalField(blank=True, decimal_places=15, max_digits=30, null=True)),
                ('y0', models.DecimalField(blank=True, decimal_places=15, max_digits=30, null=True)),
                ('x1', models.DecimalField(blank=True, decimal_places=15, max_digits=30, null=True)),
                ('y1', models.DecimalField(blank=True, decimal_places=15, max_digits=30, null=True)),
                ('epsg', models.IntegerField(blank=True, null=True)),
                ('favorite_count', models.IntegerField(default=0)),
                ('share_count', models.IntegerField(default=0)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('file', models.FileField(blank=True, max_length=255, null=True, storage=ohmg.georeference.storage.OverwriteStorage(), upload_to=ohmg.georeference.models.resources.set_upload_location)),
                ('thumbnail', models.FileField(blank=True, max_length=255, null=True, storage=ohmg.georeference.storage.OverwriteStorage(), upload_to='thumbnails')),
                ('lock_enabled', models.BooleanField(default=False)),
                ('lock_details', models.JSONField(blank=True, null=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='GCP',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('pixel_x', models.IntegerField(blank=True, null=True)),
                ('pixel_y', models.IntegerField(blank=True, null=True)),
                ('geom', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('note', models.CharField(blank=True, max_length=255, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='created_by', to=settings.AUTH_USER_MODEL)),
                ('gcp_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='georeference.gcpgroup')),
                ('last_modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='modified_by', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'GCP',
                'verbose_name_plural': 'GCPs',
            },
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
            ],
            options={
                'verbose_name': 'Document',
                'verbose_name_plural': 'Documents',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('georeference.itembase',),
        ),
        migrations.CreateModel(
            name='GeorefSession',
            fields=[
            ],
            options={
                'verbose_name': 'Georeference Session',
                'verbose_name_plural': '  Georeference Sessions',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('georeference.sessionbase',),
        ),
        migrations.CreateModel(
            name='Layer',
            fields=[
            ],
            options={
                'verbose_name': 'Layer',
                'verbose_name_plural': 'Layers',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('georeference.itembase',),
        ),
        migrations.CreateModel(
            name='PrepSession',
            fields=[
            ],
            options={
                'verbose_name': 'Preparation Session',
                'verbose_name_plural': '   Preparation Sessions',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('georeference.sessionbase',),
        ),
        migrations.AddField(
            model_name='sessionbase',
            name='doc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='doc', to='georeference.document'),
        ),
        migrations.AddField(
            model_name='sessionbase',
            name='lyr',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lyr', to='georeference.layer'),
        ),
        migrations.AddField(
            model_name='gcpgroup',
            name='doc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='georeference.document'),
        ),
        migrations.CreateModel(
            name='DocumentLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_id', models.PositiveIntegerField()),
                ('link_type', models.CharField(choices=[('split', 'split'), ('georeference', 'georeference')], max_length=25)),
                ('target_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='links', to='georeference.document')),
            ],
        ),
    ]