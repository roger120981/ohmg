import os
import base64
import logging
import psycopg2
from PIL import Image

from django.conf import settings
from django.urls import reverse

from geonode.base.models import ThesaurusKeyword
from geonode.documents.models import DocumentResourceLink
from geonode.layers.models import Layer

from .georeferencer import get_path_variant

logger = logging.getLogger(__name__)

## ~~ general utils ~~

def full_reverse(view_name, **kwargs):
    """Wraps the reverse utility to prepend the site base domain."""
    base = settings.SITEURL.rstrip("/")
    full_url = base + reverse(view_name, **kwargs)
    return full_url

def make_db_cursor():

    ## make connection to postgis database
    db = settings.DATABASES['default']
    db_conn = "dbname = {} port = {} user = {} host = {} password = {}".format(
        db['NAME'],db['PORT'],db['USER'],db['HOST'],db['PASSWORD'])
    conn = psycopg2.connect(db_conn)

    return conn.cursor()

## ~~ Status TKeyword Management ~~

def get_tk_lookup():
    tk_lookup = {
        "unprepared": ThesaurusKeyword.objects.get(about="unprepared"),
        "splitting": ThesaurusKeyword.objects.get(about="splitting"),
        "prepared": ThesaurusKeyword.objects.get(about="prepared"),
        "georeferencing": ThesaurusKeyword.objects.get(about="georeferencing"),
        "georeferenced": ThesaurusKeyword.objects.get(about="georeferenced"),
    }
    return tk_lookup

def get_status(resource):
    status = None
    tk_lookup = get_tk_lookup()
    for tk in tk_lookup.values():
        if tk in resource.tkeywords.all():
            status = tk.about
    return status

def unset_status(resource):
    tk_lookup = get_tk_lookup()
    for tk in tk_lookup.values():
        if tk in resource.tkeywords.all():
            resource.tkeywords.remove(tk)

def set_status(resource, status):
    tk_lookup = get_tk_lookup()
    unset_status(resource)
    resource.tkeywords.add(tk_lookup[status])

## ~~ IIIF support ~~

def document_as_iiif_resource(document, iiif_server=False):

    img = Image.open(document.doc_file)
    width, height = img.size

    resource = {
      "@type": "dctypes:Image",
      "width": width,
      "height": height
    }

    if iiif_server is True:
        iiif2_base = f"{settings.IIIF_SERVER_LOCATION}/iiif/2"
        fname = os.path.basename(document.doc_file.name)
        resource["@id"] = f"{iiif2_base}/{fname}/full/max/0/default.jpg",
        resource["service"] = {
            "@context": "http://iiif.io/api/image/2/context.json",
            "@id": f"{iiif2_base}/{fname}",
            "profile": "http://iiif.io/api/image/2/level2.json",
            "protocol": "http://iiif.io/api/image"
        }
    else:
        img_url = settings.SITEURL.rstrip("/") + document.doc_file.url
        resource["@id"] = img_url

    return resource

def document_as_iiif_canvas(document, resource=None, iiif_server=False):

    this_url = reverse('document_canvas', args=(document.id,))
    canvas_id = settings.SITEURL.rstrip("/") + this_url

    if resource is None:
        resource = document_as_iiif_resource(document, iiif_server=iiif_server)

    canvas = {
      "@context": "http://iiif.io/api/presentation/2/context.json",
      "@id": canvas_id,
      "@type": "sc:Canvas",
      "label": "CanvasLabel",
      "width": resource["width"],
      "height": resource["height"],
      "images": [
        {
          "@type": "oa:Annotation",
          "motivation": "sc:painting",
          "on": canvas_id,
          "resource": resource
        }
      ]
    }

    return canvas

def document_as_iiif_manifest(document, canvas=None, iiif_server=False):
    """ creates a manifest for the document's image """

    # this base64 encoding seems optional, but would probably be good to work in
    base_url = "http://localhost:8080/cantaloupe/iiii/2/"
    urlSafeEncodedBytes = base64.urlsafe_b64encode(base_url.encode("utf-8"))
    urlSafeEncodedStr = str(urlSafeEncodedBytes, "utf-8")

    this_url = reverse('document_manifest', args=(document.id,))
    manifest_id = settings.SITEURL.rstrip("/") + this_url

    if canvas is None:
        canvas = document_as_iiif_canvas(document, iiif_server=iiif_server)

    manifest = {
      "@context": "http://iiif.io/api/presentation/2/context.json",
      "@type": "sc:Manifest",
      "@id": manifest_id,
      "label": document.title,
      "description": "Description.",
      "attribution": "Attribution",
      "thumbnail": document.thumbnail_url,
      "sequences": [
        {
          "@type": "sc:Sequence",
          "canvases": [
            canvas
          ]
        }
      ]
    }

    return manifest

## ~~ Geoserver VRT utilities ~~
from geonode.geoserver.helpers import OGC_Servers_Handler
from geoserver.catalog import Catalog

def get_gs_catalog():
    """create the GeoServer catalog object"""

    ogc_server_settings = OGC_Servers_Handler(settings.OGC_SERVER)['default']

    _user, _password = ogc_server_settings.credentials

    url = ogc_server_settings.rest
    gs_catalog = Catalog(url, _user, _password,
                        retries=ogc_server_settings.MAX_RETRIES,
                        backoff_factor=ogc_server_settings.BACKOFF_FACTOR)

    return gs_catalog

def get_gs_layer_from_document(document, workspace="geonode"):

    cat = get_gs_catalog()
    doc_path = document.doc_file.path
    gs_layer_name = os.path.splitext(os.path.basename(doc_path))[0]
    gs_layer = cat.get_layer(gs_layer_name)

    return gs_layer

def create_layer_from_vrt(vrt_path, workspace="geonode"):

    cat = get_gs_catalog()
    cat._cache.clear()
    name = os.path.splitext(os.path.basename(vrt_path))[0]
    store_names = [i.name for i in cat.get_stores()]
    print(name)
    print(store_names)
    if name not in store_names:
        print("creating new store/layer")
        store = cat.create_coveragestore(name,
            path=vrt_path,
            workspace=workspace,
            type="VRT",
            overwrite=True,
            # create_layer=False
        )
        print("complete")
    else:
        store = cat.get_stores(names=name, workspaces=[workspace])[0]
    print(store)
    print(store.href)


    gs_layer = cat.get_layer(name)
    print(gs_layer)

    return {
        "name": name,
        "layer": gs_layer,
        "workspace_name": workspace,
        "store": store,
    }

## ~~ Mapserver-related functions ~~

def initialize_mapfile():

    file_path = settings.MAPSERVER_MAPFILE
    print(f"creating new mapfile: {file_path}")

    file_content = f"""MAP
NAME "Georeference Previews"
STATUS ON
EXTENT -2200000 -712631 3072800 3840000
UNITS METERS

WEB
METADATA
    "wms_title"          "GeoNode Gereferencer Preview Server"  ##required
    "wms_onlineresource" "{settings.MAPSERVER_ENDPOINT}?"   ##required
    "wms_srs"            "EPSG:3857"  ##recommended
    "wms_enable_request" "*"   ##necessary
END
END # Web

PROJECTION
"init=epsg:3857"   ##required
END

#
# Start of layer definitions
#

END # Map File
"""

    with open(file_path, "w") as out:
        out.write(file_content)

    return file_path

def mapserver_add_layer(file_path):

    vrt_path = get_path_variant(file_path, "VRT")

    mapfile = settings.MAPSERVER_MAPFILE

    if not os.path.isfile(mapfile):
        initialize_mapfile()

    layer_name = os.path.splitext(os.path.basename(vrt_path))[0]
    output = []
    already_exists = False
    with open(mapfile, "r") as openf:

        for line in openf.readlines():
            if line != "END # Map File\n":
                output.append(line)
            if vrt_path in line:
                already_exists = True
    
    if not already_exists:
        output += [
            '  LAYER\n',
            f'    NAME "{layer_name}"\n',
            '    METADATA\n',
            f'      "wms_title" "{layer_name}"\n',
            '    END\n',
            '    TYPE RASTER\n',
            '    STATUS ON\n',
            f'    DATA "{vrt_path}"\n',
            '    OFFSITE 255 255 255\n',
            '    TRANSPARENCY 100\n'
            '    PROJECTION\n',
            '     "init=epsg:3857"\n',
            '    END\n',
            '  END # Layer\n',
            # '\n',
            'END # Map File\n',
        ]
    else:
        output += ['END # Map File\n']

    with open(mapfile, "w") as openf:
        openf.writelines(output)
    
    return layer_name

def mapserver_remove_layer(file_path):

    vrt_path = get_path_variant(file_path, "VRT")
    mapfile = settings.MAPSERVER_MAPFILE

    basename = os.path.basename(vrt_path)
    output = []
    current_layer = {"source": "", "lines": []}
    with open(mapfile, "r") as openf:
        in_layer = False
        skip_layer = False
        for line in openf.readlines():

            if line == "  LAYER\n":
                in_layer = True
            
            if not in_layer:
                output.append(line)
            
            if in_layer is True:
                current_layer['lines'].append(line)

            if basename in line:
                skip_layer = True

            if line == "  END # Layer\n":
                in_layer = False
                if skip_layer is False:
                    output += current_layer['lines']
                current_layer['lines'] = []
    
    with open(mapfile, "w") as openf:
        openf.writelines(output)

