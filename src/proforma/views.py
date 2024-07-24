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
from django.http import HttpResponse, HttpResponseNotFound
from django.conf import settings
from django.template.loader import get_template
import os

from tasks.models import Task
from solutions.models import Solution

from . import api_v2
from . import api_lon_capa
from . import sandbox

from utilities.safeexec import execute_arglist
import VERSION


import logging


logger = logging.getLogger(__name__)


# external proforma entry point
@csrf_exempt  # disable csrf-cookie
def grade_api_v2(request):
    return api_v2.grade_api_v2(request)


@csrf_exempt  # disable csrf-cookie
def runtest(request):
    return api_v2.runtest(request)

@csrf_exempt  # disable csrf-cookie
def upload_v2(request):
    return api_v2.upload_v2(request)

@csrf_exempt  # disable csrf-cookie
def grade_api_lon_capa(request):
    return api_lon_capa.grade_api_lon_capa(request)


@csrf_exempt
def show_version(request):
    return HttpResponse(VERSION.version)


@csrf_exempt
def show_info(request):
    version = VERSION.version

    disk = {}

    # read disk usage for sandbox
    sandboxdir = settings.SANDBOX_DIR
    if not os.path.exists(sandboxdir):
        # sandbox folder does not exist
        disk['sandbox'] = "Sandbox folder not found"
    else:
        command = ['du', '-s', '-h']
        result = execute_arglist(args=command, working_directory=sandboxdir, timeout=60, unsafe=True)
        resultout = result[0]
        # resulterr = result[1]
        disk['sandbox'] = resultout

    database = {}
    # get number of tasks
    database['tasks'] = len(Task.objects.all())
    # get number of solutions
    database['solutions'] = len(Solution.objects.all())

    docker = sandbox.get_state()
    # print(docker)

    t = get_template('proforma/info.html')
    html_result = t.render({'database': database,
                            'disk': disk,
                            'version': version,
                            'docker': docker})
    return HttpResponse(html_result)

@csrf_exempt
def icon(request):
    return HttpResponseNotFound('icon not found')

# @api_view()
@csrf_exempt
def error_page(request):
    logger.error('invalid url: ' + request.get_full_path())
    response = HttpResponse()
    response.write('not found')
    response.status_code = 404
    return response

