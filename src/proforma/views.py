# -*- coding: utf-8 -*-

# This file is part of Ostfalia-Praktomat.
#
# Copyright (C) 2012-2019 Ostfalia University (eCULT-Team)
# http://ostfalia.de/cms/de/ecult/
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# entry points for URIs

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

import api_v2
import api_non_proforma
import VERSION


import logging


logger = logging.getLogger(__name__)


# external proforma entry point
@csrf_exempt  # disable csrf-cookie
def grade_api_v2(request):
    return api_v2.grade_api_v2(request)


@csrf_exempt  # disable csrf-cookie
def grade_api_v1(request):
    return api_non_proforma.grade_api_lon_capa(request)


@csrf_exempt
def show_version(request):
    return HttpResponse(VERSION.version)


@csrf_exempt  # NOTE: f�r Marcel danach remove;)
def test_post(request, ):
    response = HttpResponse()

    if not (request.method == "POST"):
        response.write("No Post-Request")
    else:
        postMessages = request.POST
        for key, value in postMessages.iteritems():
            response.write("Key: " + str(key) + " ,Value: " + str(value) + "\r\n")
        try:
            if not (request.FILES is None):
                response.write("List of Files: \r\n")
                for key, value in request.FILES.iteritems():
                    response.write("Key: " + str(key) + " ,Value: " + str(value) + "\r\n")
                    response.write("Content of: " + str(key) + "\r\n")
                    response.write(request.FILES[key].read() + "\r\n")
            else:
                response.write("\r\n\r\n No Files Attached")
        except Exception:
            response.write("\r\n\r\n Exception!: " + str(Exception))
    return response