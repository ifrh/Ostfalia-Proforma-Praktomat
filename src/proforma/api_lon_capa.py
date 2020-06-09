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
def get_http_error_page(title, message, callstack):
    return """<loncapagrade>
<awarddetail>ERROR</awarddetail>
<message><![CDATA[%s

%s]]></message>
</loncapagrade>
""" % (title, message)

#""" % (title, message, VERSION.version, callstack)



def grade_api_lon_capa(request,):
    logger.debug("new grading request")

    try:
        if not request.POST:
            raise Exception("No POST-Request attached")

        submission = request.POST.get("LONCAPA_student_response")
        logger.debug('submission:  ' + submission)
        submission_filename = request.POST.get("submission_filename")
        logger.debug('submission_filename:  ' + submission_filename)
        task_filename = request.POST.get("task_filename")
        logger.debug('task_filename:  ' + task_filename)
        task_file = request.POST.get("task")
        task_file = base64.b64decode(task_file)

        logger.info("grading request for task " + task_filename)

        logger.debug('import task')
        proformatask = task.import_task_internal(task_filename, task_file)

        # save solution in database
        submission_files = dict()
        submission_files.update({submission_filename: submission})
        solution = grade.save_solution(proformatask, submission_files)

        # run tests
        grade_result = grade.grade(solution, "lon_capa")

        # return result
        logger.debug("grading finished")
        response = HttpResponse()
        response.write(grade_result)
        response.status_code = 200
        return response

    except task.TaskXmlException as inst:
        logger.exception(inst)
        callstack = traceback.format_exc()
        print("TaskXmlException caught Stack Trace: " + str(callstack))
        response = HttpResponse()
        response.write(get_http_error_page('Task error', str(inst), callstack))
        response.status_code = 400 # bad request
        return response
    except Exception as inst:
        logger.exception(inst)
        callstack = traceback.format_exc()
        print("Exception caught Stack Trace: " + str(callstack))
        response = HttpResponse()
        response.write(get_http_error_page('Error in grading process', str(inst), callstack))
        response.status_code = 500 # internal error
        return response