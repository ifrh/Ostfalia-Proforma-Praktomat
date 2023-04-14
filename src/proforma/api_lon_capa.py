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
# LON-CAPA API

import traceback
from django.http import HttpResponse
import logging
from . import task
from . import grade


import base64


logger = logging.getLogger(__name__)


# string format for exception return message in HTTP
def get_http_error_page(title, message):
    return """<loncapagrade>
<awarddetail>ERROR</awarddetail>
<message><![CDATA[INTERNAL ERROR:
%s
%s]]></message>
</loncapagrade>
""" % (title, message)



def _return_error_message(inst, title):
    logger.exception(inst)
    callstack = traceback.format_exc()
    print("Exception caught Stack Trace: " + str(callstack))
    return HttpResponse(get_http_error_page(title, str(inst)), status=200)

def _get_and_check_form_field(request, name):
    field = request.POST.get(name)
    if field == None:
        raise Exception("missing Form Field in POST Request: " + name)
    # logger.debug('submission:  ' + submission)
    return field


def grade_api_lon_capa(request,):
    try:
        logger.debug("new grading request")
        # more tests in order to get a proper error messgae for the sender
        if not request.POST:
            raise Exception("No POST-Request attached")

        # get data from request
        submission = _get_and_check_form_field(request, "LONCAPA_student_response")
        submission_filename = _get_and_check_form_field(request, "submission_filename")
        task_filename = _get_and_check_form_field(request, "task_filename")
        task_file = _get_and_check_form_field(request, "task")
        task_file = base64.b64decode(task_file)

        logger.info("grading request for task " + task_filename)
    except Exception as inst:
        return _return_error_message(inst, 'Bad Request (400):')

    try:
        # create task object in database
        logger.debug('import task')
        ptask = task.Proforma_Task()
        proformatask = ptask.import_task_internal(task_filename, task_file)

        # run tests
        grader = grade.Grader(proformatask)

        submission_files = dict()
        submission_files.update({submission_filename: submission})
        grader.grade(submission_files, None, False)
        # get result
        grade_result = grader.get_result('proforma/response_loncapa.xml', False)

        # return result
        logger.debug("grading finished")
        return HttpResponse(grade_result, status = 200)

    except task.TaskXmlException as inst:
        return _return_error_message(inst, 'Bad Request/Invalid Task (400):')
    except Exception as inst:
        return _return_error_message(inst, 'Internal Server Error (500):')
