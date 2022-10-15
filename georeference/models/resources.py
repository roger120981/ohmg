import os
import uuid
import json
import logging
from osgeo import gdal, osr
from PIL import Image
from itertools import chain

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.gis.geos import Point
from django.contrib.gis.db import models
from django.contrib.gis.geos import Polygon
from django.core.files.base import ContentFile
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.utils.functional import cached_property

from geonode.documents.models import DocumentResourceLink
from geonode.documents.models import Document as GNDocument
from geonode.layers.models import Layer as GNLayer
from geonode.geoserver.helpers import save_style

from georeference.utils import (
    get_gs_catalog,
    full_reverse,
    slugify,
)
from georeference.renderers import generate_document_thumbnail_content, generate_layer_thumbnail_content
from georeference.storage import OverwriteStorage


logger = logging.getLogger(__name__)

class SplitDocumentLink(DocumentResourceLink):
    """
    Inherits from the DocumentResourceLink in GeoNode. This allows
    new instances of this model to be used by GeoNode in a default
    manner, while this app can use them in its own way.
    
    Used to create a link between split documents and their children.
    """

    class Meta:
        verbose_name = "Split Document Link"
        verbose_name_plural = "Split Document Links"

    def __str__(self):
        child = GNDocument.objects.get(pk=self.object_id)
        return f"{self.document.__str__()} --> {child.__str__()}"


class GeoreferencedDocumentLink(DocumentResourceLink):
    """
    Inherits from the DocumentResourceLink in GeoNode. This allows
    new instances of this model to be used by GeoNode in a default
    manner, while this app can use them in its own way.

    Used to create a link between georeferenced documents and the
    resulting layer.
    """

    class Meta:
        verbose_name = "Georeferenced Document Link"
        verbose_name_plural = "Georeferenced Document Links"

    def __str__(self):
        try:
            layer_name = GNLayer.objects.get(pk=self.object_id).alternate
        except GNLayer.DoesNotExist:
            layer_name = "None"
        return f"{self.document.__str__()} --> {layer_name}"


class GCP(models.Model):

    class Meta:
        verbose_name = "GCP"
        verbose_name_plural = "GCPs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pixel_x = models.IntegerField(null=True, blank=True)
    pixel_y = models.IntegerField(null=True, blank=True)
    geom = models.PointField(null=True, blank=True, srid=4326)
    note = models.CharField(null=True, blank=True, max_length=255)
    gcp_group = models.ForeignKey(
        "GCPGroup",
        on_delete=models.CASCADE)

    created = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        null=False,
        blank=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        related_name='created_by',
        on_delete=models.CASCADE)
    last_modified = models.DateTimeField(
        auto_now=True,
        editable=False,
        null=False,
        blank=False)
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        related_name='modified_by',
        on_delete=models.CASCADE)


class GCPGroup(models.Model):

    TRANSFORMATION_CHOICES = (
        ("tps", "tps"),
        ("poly1", "poly1"),
        ("poly2", "poly2"),
        ("poly3", "poly3"),
    )

    class Meta:
        verbose_name = "GCP Group"
        verbose_name_plural = "GCP Groups"

    document = models.ForeignKey(
        GNDocument,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    doc = models.ForeignKey(
        "Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    crs_epsg = models.IntegerField(null=True, blank=True)
    transformation = models.CharField(
        null=True,
        blank=True,
        choices=TRANSFORMATION_CHOICES,
        max_length=20,
    )

    def __str__(self):
        return self.document.title

    @property
    def gcps(self):
        return GCP.objects.filter(gcp_group=self)

    @property
    def gdal_gcps(self):
        gcp_list = []
        for gcp in self.gcps:
            geom = gcp.geom.clone()
            geom.transform(self.crs_epsg)
            p = gdal.GCP(geom.x, geom.y, 0, gcp.pixel_x, gcp.pixel_y)
            gcp_list.append(p)
        return gcp_list

    @property
    def as_geojson(self):

        geo_json = {
          "type": "FeatureCollection",
          "features": []
        }

        for gcp in self.gcps:
            coords = json.loads(gcp.geom.geojson)["coordinates"]
            lat = coords[0]
            lng = coords[1]
            geo_json['features'].append({
                "type": "Feature",
                "properties": {
                  "id": str(gcp.pk),
                  "image": [gcp.pixel_x, gcp.pixel_y],
                  "username": gcp.last_modified_by.username,
                  "note": gcp.note,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                }
            })
        return geo_json

    def as_points_file(self):

        content = "mapX,mapY,pixelX,pixelY,enable\n"
        for gcp in self.gcps:
            geom = gcp.geom.clone()
            geom.transform(self.crs_epsg)
            # pixel_y must be inverted b/c qgis puts origin at top left corner
            content += f"{geom.x},{geom.y},{gcp.pixel_x},-{gcp.pixel_y},1\n"

        return content

    def save_from_geojson(self, geojson, document, transformation=None):

        group, group_created = GCPGroup.objects.get_or_create(document=document)

        group.crs_epsg = 3857 # don't see this changing any time soon...
        group.transformation = transformation
        group.save()

        gcps_new, gcps_mod, gcps_del = 0, 0, 0

        # first remove any existing gcps that have been deleted
        for gcp in group.gcps:
            if str(gcp.id) not in [i['properties'].get('id') for i in geojson['features']]:
                gcps_del += 0
                gcp.delete()

        for feature in geojson['features']:

            id = feature['properties'].get('id', str(uuid.uuid4()))
            username = feature['properties'].get('username')
            user = get_user_model().objects.get(username=username)
            gcp, created = GCP.objects.get_or_create(
                id = id,
                defaults = {
                    'gcp_group': group,
                    'created_by': user
                })
            if created:
                gcps_new += 1

            pixel_x = feature['properties']['image'][0]
            pixel_y = feature['properties']['image'][1]
            new_pixel = (pixel_x, pixel_y)
            old_pixel = (gcp.pixel_x, gcp.pixel_y)
            lng = feature['geometry']['coordinates'][0]
            lat = feature['geometry']['coordinates'][1]

            new_geom = Point(lat, lng, srid=4326)

            # only update the point if one of its coordinate pairs have changed,
            # this also triggered when new GCPs have None for pixels and geom.
            if new_pixel != old_pixel or not new_geom.equals(gcp.geom) or gcp.note != feature['properties']['note']:
                gcp.note = feature['properties']['note']
                gcp.pixel_x = new_pixel[0]
                gcp.pixel_y = new_pixel[1]
                gcp.geom = new_geom
                gcp.last_modified_by = user
                gcp.save()
                if not created:
                    gcps_mod += 1
        gcps_ct = len(geojson['features'])
        logger.info(f"GCPGroup {group.pk} | GCPs ct: {gcps_ct}, new: {gcps_new}, mod: {gcps_mod}, del: {gcps_del}")
        return group

    def save_from_annotation(self, annotation, document):

        m = "georeference-ground-control-points"
        georef_annos = [i for i in annotation['items'] if i['motivation'] == m]
        anno = georef_annos[0]

        self.save_from_geojson(anno['body'], document, "poly1")


class LayerMask(models.Model):

    layer = models.ForeignKey(GNLayer, on_delete=models.CASCADE)
    polygon = models.PolygonField(srid=3857)

    def as_sld(self, indent=False):

        sld = f'''<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
 xsi:schemaLocation="http://www.opengis.net/sld StyledLayerDescriptor.xsd"
 xmlns="http://www.opengis.net/sld"
 xmlns:ogc="http://www.opengis.net/ogc"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<NamedLayer>
 <Name>{self.layer.workspace}:{self.layer.name}</Name>
 <UserStyle IsDefault="true">
  <FeatureTypeStyle>
   <Transformation>
    <ogc:Function name="gs:CropCoverage">
     <ogc:Function name="parameter">
      <ogc:Literal>coverage</ogc:Literal>
     </ogc:Function>
     <ogc:Function name="parameter">
      <ogc:Literal>cropShape</ogc:Literal>
      <ogc:Literal>{self.polygon.wkt}</ogc:Literal>
     </ogc:Function>
    </ogc:Function>
   </Transformation>
   <Rule>
    <RasterSymbolizer>
      <Opacity>1</Opacity>
    </RasterSymbolizer>
   </Rule>
  </FeatureTypeStyle>
 </UserStyle>
</NamedLayer>
</StyledLayerDescriptor>'''

        if indent is False:
            sld = " ".join([i.strip() for i in sld.splitlines()])
            sld = sld.replace("> <","><")

        return sld

    def apply_mask(self):

        cat = get_gs_catalog()

        gs_full_style = cat.get_style(self.layer.name, workspace="geonode")
        trim_style_name = f"{self.layer.name}_trim"

        # create (overwrite if existing) trim style in GeoServer using mask sld
        gs_trim_style = cat.create_style(
            trim_style_name,
            self.as_sld(),
            overwrite=True,
            workspace="geonode",
        )

        # get the GeoServer layer for this GeoNode layer
        gs_layer = cat.get_layer(self.layer.name)

        # add the full and trim styles to the GeoServer alternate style list
        gs_alt_styles = gs_layer._get_alternate_styles()
        gs_alt_styles += [gs_full_style, gs_trim_style]
        gs_layer._set_alternate_styles(gs_alt_styles)

        # set the trim style as the default in GeoServer
        gs_layer._set_default_style(gs_trim_style)

        # save these changes to the GeoServer layer
        cat.save(gs_layer)

        # create/update the GeoNode Style object for the trim style
        trim_style_gn = save_style(gs_trim_style, self.layer)

        # add new trim style to GeoNode list styles, set as default, save
        self.layer.styles.add(trim_style_gn)
        self.layer.default_style = trim_style_gn
        self.layer.save()

        # update thumbnail with new trim style
#        thumb = create_thumbnail(self.layer, overwrite=True)
#        self.layer.thumbnail_url = thumb
#        self.layer.save()

class DocumentManager(models.Manager):

    _type = 'document'

    def get_queryset(self):
        return super(DocumentManager, self).get_queryset().filter(type=self._type)

    def create(self, **kwargs):
        kwargs.update({
            'type': self._type,
        })
        return super(DocumentManager, self).create(**kwargs)


class LayerManager(models.Manager):

    _type = 'layer'

    def get_queryset(self):
        return super(LayerManager, self).get_queryset().filter(type=self._type)

    def create(self, **kwargs):
        kwargs.update({
            'type': self._type,
        })
        return super(LayerManager, self).create(**kwargs)

def set_upload_location(instance, filename):
    """ this function has to return the location to upload the file """
    return os.path.join(f"{instance.type}s", filename)

class ItemBase(models.Model):

    GEOREF_STATUS_CHOICES = (
        ("unprepared", "Unprepared"),
        ("needs review", "Needs Review"),
        ("splitting", "Splitting - in progress"),
        ("split", "Split"),
        ("prepared", "Prepared"),
        ("georeferencing", "Georeferencing - in progress"),
        ("georeferenced", "Georeferenced"),
    )

    title = models.CharField(_('title'), max_length=255)
    slug = models.CharField(
        max_length=128, null=True, blank=True
    )
    type = models.CharField(
        max_length=10,
        choices=(("document", "Document"), ("layer", "Layer")),
    )
    date = models.DateTimeField(
        default=timezone.now
    )
    attribution = models.CharField(
        max_length=2048,
        blank=True,
        null=True,
    )
    status = models.CharField(
        blank=True,
        null=True,
        max_length=50,
        default=GEOREF_STATUS_CHOICES[0][0],
        choices=GEOREF_STATUS_CHOICES
    )

    x0 = models.DecimalField(
        max_digits=30,
        decimal_places=15,
        blank=True,
        null=True
    )
    y0 = models.DecimalField(
        max_digits=30,
        decimal_places=15,
        blank=True,
        null=True
    )
    x1 = models.DecimalField(
        max_digits=30,
        decimal_places=15,
        blank=True,
        null=True
    )
    y1 = models.DecimalField(
        max_digits=30,
        decimal_places=15,
        blank=True,
        null=True
    )

    epsg = models.IntegerField(
        blank=True,
        null=True,
    )

    favorite_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True, null=True, blank=True)

    file = models.FileField(
        upload_to=set_upload_location,
        null=True,
        blank=True,
        max_length=255,
        storage=OverwriteStorage(),
    )
    thumbnail = models.FileField(
        upload_to='thumbnails',
        null=True,
        blank=True,
        max_length=255,
        storage=OverwriteStorage(),
    )

    def __str__(self):
        return str(self.title)

    @property
    def _base_urls(self):
        return {
            "thumbnail": self.thumbnail.url if self.thumbnail else "",
            "image": self.file.url if self.file else "",
        }

    @property
    def bbox(self):
        """BBOX is in the format: [x0, x1, y0, y1, srid]."""
        if self.extent:
            xmin, ymin, xmax, ymax = self.extent
            return [xmin, xmax, ymin, ymax, "EPSG:4326"]
        else:
            return [-180, 180, -90, 90, "EPSG:4326"]

    @property
    def extent(self):
        """ returns an extent tuple """
        extent = None
        if self.x0 is not None:
            extent = (
                float(self.x0),
                float(self.y0),
                float(self.x1),
                float(self.y1)
            )
        return extent

    def set_thumbnail(self):
        if self.file is not None:
            path = self.file.path
            name = os.path.splitext(os.path.basename(path))[0]
            if self.type == "document":
                content = generate_document_thumbnail_content(path)
                tname = f"{name}-doc-thumb.png"
            elif self.type == "layer":
                content = generate_layer_thumbnail_content(path)
                tname = f"{name}-lyr-thumb.png"
            else:
                return None
            self.thumbnail.save(tname, ContentFile(content))

    def set_extent(self):
        """ https://gis.stackexchange.com/a/201320/28414 """
        if self.file is not None:
            src = gdal.Open(self.file.path)
            ulx, xres, xskew, uly, yskew, yres  = src.GetGeoTransform()
            lrx = ulx + (src.RasterXSize * xres)
            lry = uly + (src.RasterYSize * yres)

            src = None
            del src

            webMerc = osr.SpatialReference()
            webMerc.ImportFromEPSG(3857)
            wgs84 = osr.SpatialReference()
            wgs84.ImportFromEPSG(4326)
            transform = osr.CoordinateTransformation(webMerc, wgs84)

            ul = transform.TransformPoint(ulx, uly)
            lr = transform.TransformPoint(lrx, lry)

            self.x0 = ul[1]
            self.y0 = lr[0]
            self.x1 = lr[1]
            self.y1 = ul[0]

    def save(self, *args, **kwargs):

        set_slug = kwargs.get("set_slug", False)
        if set_slug or not self.slug:
            self.slug = slugify(self.title, join_char="_")

        set_thumbnail = kwargs.get("set_thumbnail", False)
        if set_thumbnail or (self.file and not self.thumbnail):
            self.set_thumbnail()

        set_extent = kwargs.get("set_extent", False)
        if set_extent or (self.type == "layer" and self.file and not self.x0):
            self.set_extent()

        return super(ItemBase, self).save(*args, **kwargs)

class Document(ItemBase):

    objects = DocumentManager()

    class Meta:
        proxy = True
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    @cached_property
    def image_size(self):
        if self.file:
            img = Image.open(self.file)
            size = img.size
            img.close()
        else:
            size = None
        return size

    @property
    def urls(self):
        urls = self._base_urls
        urls.update({
            "detail": f"/documents/{self.pk}",
            "progress_page": f"/documents/{self.pk}#georeference",
            "split": full_reverse("split_view", args=(self.pk, )),
            "georeference": full_reverse("georeference_view", args=(self.pk, )),
        })
        return urls

    @property
    def preparation_session(self):
        from georeference.models.sessions import PrepSession
        try:
            return PrepSession.objects.get(doc=self)
        except PrepSession.DoesNotExist:
            if self.parent is not None:
                return self.parent.preparation_session
            else:
                return None
        except PrepSession.MultipleObjectsReturned:
            logger.warn(f"Multiple PrepSessions found for Document {self.id}")
            return list(PrepSession.objects.filter(doc=self))[0]

    @property
    def cutlines(self):
        cutlines = []
        if not self.parent and self.preparation_session:
            cutlines = self.preparation_session.data['cutlines']
        return cutlines

    @cached_property
    def parent(self):
        try:
            link = DocumentLink.objects.get(target_id=self.pk, link_type="split")
            parent = link.source
        except DocumentLink.DoesNotExist:
            parent = None
        return parent

    @cached_property
    def children(self):
        links = DocumentLink.objects.filter(source=self, link_type="split")
        return [i.target for i in links]

    @cached_property
    def gcp_group(self):
        try:
            return GCPGroup.objects.get(doc=self.id)
        except GCPGroup.DoesNotExist:
            return None

    @property
    def gcps_geojson(self):
        gcp_group = self.gcp_group
        if gcp_group is not None:
            return gcp_group.as_geojson
        else:
            return None

    @property
    def transformation(self):
        gcp_group = self.gcp_group
        if gcp_group is not None:
            return gcp_group.transformation
        else:
            return None

    def get_extended_urls(self):
        urls = self.urls
        urls.update(self.get_layer_urls())
        return urls

    def get_sessions(self, serialize=False):

        ps = self.preparation_session
        if ps is not None:
            from georeference.models.sessions import GeorefSession
            gs = GeorefSession.objects.filter(doc=self).order_by("date_run")
            sessions = list(chain([ps], gs))
            if serialize is True:
                return [i.serialize() for i in sessions]
            else:
                return sessions
        else:
            return []

    def get_layer(self):
        try:
            link = DocumentLink.objects.get(link_type="georeference", source=self)
            layer = link.target
        except DocumentLink.DoesNotExist:
            layer = None
        return layer

    def serialize(self, serialize_children=True, serialize_parent=True, serialize_layer=True):

        parent = None
        if self.parent is not None:
            if serialize_parent:
                parent = self.parent.serialize(serialize_children=False, serialize_layer=serialize_layer)
            else:
                parent = self.parent.pk

        children = None
        if len(self.children) > 0:
            if serialize_children:
                children = [i.serialize(serialize_parent=False, serialize_layer=serialize_layer) for i in self.children]
            else:
                children = [i.pk for i in self.children]

        layer = self.get_layer()
        if layer is not None:
            if serialize_layer:
                layer = layer.serialize(serialize_document=False)
            else:
                layer = layer.slug

        return {
            "id": self.pk,
            "title": self.title,
            "slug": self.slug,
            "status": self.status,
            "urls": self.urls,
            "image_size": self.image_size,
            "cutlines": self.cutlines,
            "parent": parent,
            "children": children,
            "layer": layer,
            "gcps_geojson": self.gcps_geojson,
            "transformation": self.transformation
            # "lock": self.lock.as_dict,
        }

class Layer(ItemBase):

    objects = LayerManager()

    class Meta:
        proxy = True
        verbose_name = "Layer"
        verbose_name_plural = "Layers"

    @property
    def urls(self):
        urls = self._base_urls
        georef_url = self.get_document().urls['georeference']
        urls.update({
            # note the geonode: prefix is still necessary until non-geonode
            # layer and document detail pages are created.
            "detail": f"/layers/geonode:{self.slug}" if self.slug else "",
            "progress_page": f"/layers/geonode:{self.pk}#georeference" if self.slug else "",
            # redundant, I know, but a patch for now
            "cog": settings.MEDIA_HOST.rstrip("/") + urls['image'],
            "georeference": georef_url,
        })
        return urls

    # not currently in used, but retained as a placeholder for the future
    def get_ohm_url(self):
        try:
            tms_url = f"https://oldinsurancemaps.net/geoserver/gwc/service/tms/1.0.0/{lp.alternate}/{{z}}/{{x}}/{{-y}}.png"
            centroid = Polygon().from_bbox(self.extent).centroid
            ohm_url = f"https://www.openhistoricalmap.org/edit#map=15/{centroid.coords[1]}/{centroid.coords[0]}&background=custom:{tms_url}"
            return ohm_url
        except Exception as e:
            print("ERROR:")
            print(e)
            return "https://www.openhistoricalmap.org/edit"

    def get_document(self):
        try:
            link = DocumentLink.objects.get(link_type="georeference", target_id=self.pk)
            document = link.source
        except DocumentLink.DoesNotExist:
            document = None
        return document

    def serialize(self, serialize_document=True):

        document = self.get_document()
        if document is not None:
            if serialize_document is True:
                document = document.serialize(serialize_layer=False)
            else:
                document = document.pk

        return {
            "id": self.pk,
            "title": self.title,
            "slug": self.slug,
            "status": self.status,
            "urls": self.urls,
            "document": document,
            "extent": self.extent,
            # "lock": self.lock.as_dict,
        }

LINK_TYPE_CHOICES = (
    ("split","split"),
    ("georeference","georeference"),
)

class DocumentLink(models.Model):
    """Holds a linkage between a Document and another item. This model
    is essentially identical to DocumentResourceLink in GeoNode 3.2."""

    source = models.ForeignKey(
        Document,
        related_name='links',
        on_delete=models.CASCADE
    )
    target_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_type', 'target_id')
    link_type = models.CharField(
        choices = LINK_TYPE_CHOICES,
        max_length=25,
    )

    def __str__(self):
        return f"{self.source} --> {self.target}"
