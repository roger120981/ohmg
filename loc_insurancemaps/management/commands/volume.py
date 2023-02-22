from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from loc_insurancemaps.tasks import generate_mosaic_geotiff_as_task
from loc_insurancemaps.management.volume import (
    import_volume,
    generate_mosaic_geotiff,
    generate_mosaic_json,
)
from loc_insurancemaps.models import Volume, Place

class Command(BaseCommand):
    help = 'command to search the Library of Congress API.'

    def add_arguments(self, parser):
        parser.add_argument(
            "operation",
            choices=[
                "import",
                "refresh-lookups-old",
                "refresh-lookups",
                "make-sheets",
                "generate-mosaic",
                "generate-mosaic-json",
            ],
            help="the operation to perform",
        ),
        parser.add_argument(
            "-i", "--identifier",
            help="the identifier of the LoC resource to add",
        ),
        parser.add_argument(
            "--load-documents",
            action="store_true",
            help="boolean to indicate whether documents should be made for the sheets",
        ),
        parser.add_argument(
            "--background",
            action="store_true",
            help="run the operation in the background with celery"
        )
        parser.add_argument(
            "--username",
            help="username to use for load operation"
        )
        parser.add_argument(
            "--locale",
            help="slug for the Place to attach to this volume"
        )

    def handle(self, *args, **options):

        if options['username']:
            username = options['username']
        else:
            username = "admin"
        user = get_user_model().objects.get(username=username)

        i = options['identifier']
        if options['operation'] == "refresh-lookups":
            if i is not None:
                vols = Volume.objects.filter(pk=i)
            else:
                vols = Volume.objects.all()
            for v in vols:
                v.refresh_lookups()
            print(f"refreshed lookups on {len(vols)} volumes")

        if options['operation'] == "refresh-lookups-old":
            if i is not None:
                vols = Volume.objects.filter(pk=i)
            else:
                vols = Volume.objects.all()
            for v in vols:
                v.populate_lookups()
            print(f"refreshed lookups on {len(vols)} volumes")

        if options['operation'] == "import":

            locale_slug = options['locale']
            locale = None
            if locale_slug is not None:
                try:
                    print(f'locale slug: {locale_slug}')
                    locale = Place.objects.get(slug=locale_slug)
                    print(f'using locale: {locale}')
                except Place.DoesNotExist:
                    confirm = input('no locale matching this slug, locale will be None. continue? y/N ')
                    if not confirm.lower().startswith("y"):
                        exit()

            vol = import_volume(i, locale=locale)
            print(vol)

        if options['operation'] == "make-sheets":
            vol = Volume.objects.get(pk=i)
            vol.make_sheets()
            if options['load_documents']:
                vol.loaded_by = user
                vol.load_date = datetime.now()
                vol.save(update_fields=["loaded_by", "load_date"])
                vol.load_sheet_docs(force_reload=True)

        if options['operation'] == "generate-mosaic":
            if i is not None:
                if options['background']:
                    generate_mosaic_geotiff_as_task.apply_async(
                        (i, ),
                        queue="update"
                    )
                else:
                    generate_mosaic_geotiff(i)

        if options['operation'] == "generate-mosaic-json":
            if i is not None:
                generate_mosaic_json(i)
