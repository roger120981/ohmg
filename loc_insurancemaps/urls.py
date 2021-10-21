# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2017 OSGeo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

from django.conf import settings
from django.urls import path
from django.conf.urls import url, include
from django.views.generic import TemplateView

from geonode.urls import urlpatterns
from geonode.monitoring import register_url_event

from .views import item_detail, SimpleAPI, VolumeDetail, HomePage

urlpatterns += [
    path('lc/volume/<str:docdoi>/', item_detail, {"loc_type": "volume"}, name='volume_detail'),
    path('lc/sheet/<str:docdoi>/', item_detail, {"loc_type": "sheet"}, name='sheet_detail'),
    path('lc/api/', SimpleAPI.as_view() , name='lc_api'),
    path('lc/<str:volumeid>/', VolumeDetail.as_view(), name="volume_summary"),
]

if 'georeference' in settings.INSTALLED_APPS:
    urlpatterns += [url(r'^g/', include('georeference.urls'))]

homepage = register_url_event()(HomePage.as_view())

urlpatterns = [
    url(r'^/?$', homepage, name='home'),
 ] + urlpatterns