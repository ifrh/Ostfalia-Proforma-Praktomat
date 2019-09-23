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
# functions for grading a student's submission

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render_to_response
from django.contrib.auth import login
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage

from accounts.templatetags.in_group import in_group
from tasks.models import Task
from accounts.models import User
from utilities import encoding
from urllib2 import Request, urlopen, URLError, HTTPError
from solutions.models import Solution, SolutionFile
from VERSION import version

from django.template.loader import render_to_string

import mimetypes
import os
import codecs
import re
import logging
import chardet
import traceback
#import proforma.api_v2

from solutions.forms import SolutionFormSet

logger = logging.getLogger(__name__)

def get_http_error_page(title, message, callstack):
    return """%s

    %s

Callstack:
    %s""" % (title, message, callstack)


# internal proforma entry point
@csrf_exempt  # disable csrf-cookie
def file_grader_post(request, response_format, task_id=None):
    try:

        logger.debug("file_grader_post start")

        DEFINED_USER = "sys_prod"
        ziptype_re = re.compile(r'^application/(zip|x-zip|x-zip-compressed|x-compressed)$')

        response = HttpResponse()
        # save files
        # start grading

        # check post
        if request.method != 'POST':
            raise Exception("No POST-Request")

        postData = request.POST.copy()

        #if len(postData) > 1:
        #    result_message = "Error: Please only one file "
        #    response.write(result_page(award="ERROR", message=result_message))
        #    return response

        #check if task exist
        if not check_task_id(task_id):
            raise Exception("task does not exist. Task number " +  str(task_id))

        #check if user is authenticated if not login
        if not request.user.is_authenticated():
            if authenticate_user(DEFINED_USER, request) is None:
                raise Exception("system user does not exist")

        #create task_object for submitting data
        task = get_object_or_404(Task, pk=task_id)
        supported_types_re = re.compile(task.supported_file_types)

        fileNameList = []
        DataNameList = []
        fileDict = dict()
        for filename, file in request.FILES.iteritems():
            fileNameList.append(str(filename))
            DataNameList.append(str(file.name))
            actualFileName = re.search(r"([\w\.\-]+)$", filename, re.MULTILINE)
            contentType = mimetypes.guess_type(filename)[0]  #todo: really?
            if not actualFileName:
                raise Exception("Incorrect filename")

            if (contentType is None) or (not (supported_types_re.match(contentType) or ziptype_re.match(contentType))):
                result_message = "Mime-type %s is not supported by this task" % contentType
                raise Exception(result_message)

            try:
                filename.decode('ascii')
                fileDict[str(filename)] = file
            except UnicodeEncodeError:
                raise Exception("filename must not contain any special characters:" + filename)

        #two lists with fileName and DataName

        solution = initSolution(request, task)

        # todo: copy from solution/views -> files from form could use default checks
        # formset = SolutionFormSet(solution, request.FILES, instance=solution)
        saveSolution(solution, fileDict)
        result, solution = gradeSolution(solution)
        lcxml = get_solution_xml(result, solution, fileNameList, response_format)

        logger.debug("file_grader_post finished")

        return HttpResponse(lcxml)

        #result_message = "Everything is fine"
        #response.write(result_page(award="CORRECT", message=result_message))
        #response.status_code = 200
        #return response

    except Exception as inst:
        logger.exception(inst)
        callstack = traceback.format_exc()
        #print "Exception caught Stack Trace: " + str(callstack)  # __str__ allows args to be printed directly

        #result_message = str(inst) + "\n" + callstack
        response.write(get_http_error_page('Error in grading process', str(inst), callstack))
        response.status_code = 500 # internal error
        return response


# try and guess the correct JAVA path name derived from the package that
# is declared in the source code
def find_java_package_path(file_content):
    # logger.debug('file_content' + file_content)
    # remove comment with /* */
    file_content = re.sub(r'\/\*[\s\S]*?\*\/', '', file_content, re.MULTILINE)
    file_content = re.sub(r'\/\/.*', '', file_content, re.MULTILINE)

    pattern = re.compile('package([\s\S]*?);')
    m = pattern.search(file_content)
    try:
        package = m.group(2).strip()
    except:
        try:
            package = m.group(1).strip()
        except:
            logger.debug("no package found")
            return ''

    package = re.sub('\.', '/', package)
    logger.debug("package path: " + package)
    return package

def grader_internal(task_id, files, response_format):
    # check if task exist
    if not check_task_id(task_id):
        raise Exception("task does not exist. Task number " + str(task_id))

    DEFINED_USER = "sys_prod"
    ziptype_re = re.compile(r'^application/(zip|x-zip|x-zip-compressed|x-compressed)$')

    response = HttpResponse()
    # save files
    # start grading


    # check if user is authenticated if not login
    #if not request.user.is_authenticated():
    #    if authenticate_user(DEFINED_USER, request) is None:
    #        raise Exception("system user does not exist")

    #create task_object for submitting data
    task = get_object_or_404(Task, pk=task_id)
    supported_types_re = re.compile(task.supported_file_types)

    #print files
    fileDict = dict()
    fileNameList = []
    fileDict = files
    #fileDict["submission.zip"] = files["submission.zip"]
    fileNameList.append("submission.zip")

    # DataNameList = []
    #
    # for filename, file in files:
    #     fileNameList.append(str(filename))
    #     DataNameList.append(str(file.name))
    #     actualFileName = re.search(r"([\w\.\-]+)$", filename, re.MULTILINE)
    #     contentType = mimetypes.guess_type(filename)[0]  # todo: really?
    #     if not actualFileName:
    #         raise Exception("Incorrect filename")
    #
    #     if (contentType is None) or (not (supported_types_re.match(contentType) or ziptype_re.match(contentType))):
    #         result_message = "Mime-type %s is not supported by this task" % contentType
    #         raise Exception(result_message)
    #
    #     try:
    #         filename.decode('ascii')
    #         fileDict[str(filename)] = file
    #     except UnicodeEncodeError:
    #         raise Exception("filename must not contain any special characters:" + filename)

    # two lists with fileName and DataName

    #solution = initSolution(request, task)

    user_id = None
    #author = get_object_or_404(User, pk=user_id) \
    #    if user_id else request.user # todo: Ablauf checken vielleicht nur request.user?
    #author = get_object_or_404(User, pk=user_id)
    sysProd = User.objects.get(username=DEFINED_USER)
    #solution object for submission
    logger.debug("save solution")

    solution = Solution(task=task, author=sysProd)
    #save the solution model in the database
    solution.save()


    # todo: copy from solution/views -> files from form could use default checks
    # formset = SolutionFormSet(solution, request.FILES, instance=solution)
    saveSolution(solution, fileDict)
    logger.debug("grade solution")
    result, solution = gradeSolution(solution)
    lcxml = get_solution_xml(result, solution, fileNameList, response_format)

    logger.debug("file_grader_post finished")

    return lcxml #HttpResponse(lcxml)




def initSolution(request, task):
    #create author_object for submitting data
    user_id = None
    author = get_object_or_404(User,
                               pk=user_id) if user_id else request.user # todo: Ablauf checken vielleicht nur request.user?
    #solution object for submission
    solution = Solution(task=task, author=author)
    #save the solution model in the database
    solution.save()

    return solution


def saveSolution(solution, fileDict):

    for index in range(len(fileDict)):
        # create solution_file
        solution_file = SolutionFile(solution=solution)

        #save solution in enviroment and get the path
        filename = fileDict.keys()[index]
        logger.debug('save file ' + filename)
        #logger.debug('-> save file ' + filename + ': <' + str(fileDict.values()[index]) + '>')
        data = fileDict.values()[index]
        #data = fileDict.values()[index].read()
        saved_solution = save_file(data, solution_file, filename)
        #remove the upload path /home/ecult/devel_oli/upload
        shorter_saved_solution = saved_solution[len(settings.UPLOAD_ROOT):]  # todo besser +1 und doku
        #remove the beginnning slash -> relative path
        super_short_solution = shorter_saved_solution[1:]
        #save solution file
        solution_file.file = super_short_solution
        solution_file.save()


def gradeSolution(solution):
    #start the checking process
    logger.debug('execute checks')
    solution.check(True)
    #get result object
    logger.debug('get results...')
    result = solution.allCheckerResults()
    return result, solution


# @csrf_exempt  # disable csrf-cookie
# def text_grader(request, user_name=None, task_id=None, file_name=None, lms=None):
#     """
#
#     :param request:
#     :param user_name:
#     :param task_id:
#     :param file_name:
#     :return:
#     """
#     response = HttpResponse()
#     result_message = ""
#     DEFINED_USER = "sys_prod"  # username in praktomat
#     DEFINED_FILENAME = "submit.java"
#     response_format = "loncapa"
#     # todo: user_name erase
#
#     if file_name is None:
#         file_name = DEFINED_FILENAME
#     else:
#         try:
#             # only ascii characters are allowed
#             file_name = file_name.encode("utf-8")
#         except UnicodeEncodeError:
#             result_message = "Der Text darf keine Sonderzeichen enthalten"
#             response.write(result_page(award="ERROR", message=result_message))
#             response.status_code = 200
#             return response
#
#     # check if task exist
#     if not check_task_id(task_id):
#         response.write(error_page(1))
#         response.status_code = 200
#         return response
#
#     #create task_object for submitting data
#     task = get_object_or_404(Task, pk=task_id)
#
#     if request.POST:  # check if it is a POST.Request
#         student_response = request.POST.get('LONCAPA_student_response')  # get string of post-message
#         if not student_response:
#             result_message = "Keine Einreichung angegeben"
#             response.write(result_page(award="ERROR", message=result_message))
#             response.status_code = 200
#             return response
#             #  todo: max file size? anything i should remove?
#     else:
#         result_message = "Keine Einreichung angegeben"
#         response.write(result_page(award="ERROR", message=result_message))
#         response.status_code = 200
#         return response
#
#     #check if user is authenticated if not login
#     if not request.user.is_authenticated():
#         if authenticate_user(DEFINED_USER, request) is None:
#             result_message = "Der System_User existiert nicht auf dem Bewertungssystem"
#             response.write(result_page(award="ERROR", message=result_message))
#             response.status_code = 200
#             return response
#     try:
#         result, solution = grade_task(student_response, request, file_name, task)
#     except Exception as e:
#         result_message = "%s" % e
#         response.write(result_page(award="ERROR", message=result_message))
#         response.status_code = 200
#         return response
#         #result printing
#
#     if lms == 'lcxml':
#         fileList = list()
#         fileList.append(file_name)  # one file is the exception -> list needed
#         lcxml = get_solution_xml(result, solution, fileList, response_format)
#         return HttpResponse(lcxml)
#     else:
#         result_award, result_message = get_solution(result, result_message, solution)  # print submitted files
#         #print_submitted_files
#         result_message = print_submitted_files(result_message, solution, file_name)
#
#         response.write(result_page(award=result_award, message=result_message))
#         response.status_code = 200
#     return response



def save_file(data, solution_file, filename):
    """

    :param data:
    :param solution_file:
    :param filename:
    """

    solution_file.mime_type = get_mimetype(
        filename)  # just define it it will be tested later todo: method wo es passiert
    solution = solution_file.solution
    full_directory = settings.UPLOAD_ROOT + '/SolutionArchive/Task_' + unicode(
        solution.task.id) + '/User_' + solution.author.username + '/Solution_' + unicode(
        solution.id) + '/'      # directory structure from solution.model
    full_filename = os.path.join(full_directory, filename)
    path = os.path.dirname(full_filename)
    if not os.path.exists(path):
        os.makedirs(path)

    if (filename[-3:].upper() == 'ZIP') or (filename[-3:].upper() == 'JAR'):
        fd = open('%s' % (full_filename), 'wb')
        fd.write(data)
        fd.close()
    else:
        logger.debug('File content class name is ' + data.__class__.__name__)
        if data.__class__.__name__ == 'InMemoryUploadedFile':
            with default_storage.open('%s' % (full_filename), 'w') as destination:
                for chunk in data.chunks():
                    destination.write(chunk)
        elif data.__class__.__name__ == 'File':
            logger.debug('File name is ' + data.name)
            if full_filename.lower().endswith('.java'):
                # special handling for java files:
                # check for package and move to appropriate path
                short_filename = os.path.basename(filename)
                if filename == short_filename:
                    # filename does not contain a package yet
                    data.seek(0) # set file pointer to the beginning of the file
                    file_content = data.read()
                    # logger.debug('look for package path ')
                    package = find_java_package_path(file_content)
                    if len(package) > 0:
                        logger.debug('prepend package path ' + package)
                        full_filename = os.path.join(full_directory,  package + '/' + filename)

            logger.debug('full_filename name is ' + full_filename)
            tmp = default_storage.save(full_filename, data)
            logger.debug('save returned ' + tmp)


        elif data.__class__.__name__ == 'str':
            fd = open('%s' % (full_filename), 'w')
            fd.write(data)
            fd.close()
        elif data.__class__.__name__ == 'unicode':
            fd = open('%s' % (full_filename), 'w')
            fd.write(data.encode("utf-8"))
            fd.close()
        else:
            # string
            #fd = codecs.open('%s' % (full_filename), 'wb', "utf-8")
            #fd.write(data)
            #fd.close()
            fd = open('%s' % (full_filename), 'w')
            fd.write(data) ## .encode("utf-8"))
            fd.close()

    return full_filename


def check_task_id(task_id):
    """
    check_task_id(task_id)
    return task object or None
    """
    try:
        task = Task.objects.get(pk=task_id)
        return task
    except ObjectDoesNotExist:
        return None


def get_mimetype(txt):
    """
    :param txt:
    :return:
    """
    # Mimetype overwrite while saving -> ok to define mime as text
    # todo: use mimetypes.guess_type
    return 'text/plain'


# def error_page(error_code):
#     """
#     error_page(error_code)
#     return (LON-CAPA ERROR RESPONSE)
#
#     error_code 1: task does not exist
#     error_code 2: no data is send to script
#     error_code 3: server couldn\'t fulfill the request. (get_data)
#     """
#     # todo: instead of using if-statements use switch-statement
#     if error_code == 1:
#         award = "ERROR"
#         message = "task does not exist"
#     elif error_code == 2:
#         award = "INTERNAL_ERROR"
#         message = "no data is send to script"
#     elif error_code == 3:
#         award = "INTERNAL_ERROR"
#         message = "server couldn\'t fulfill the request. (get_data)"
#     elif error_code == 4:
#         award = "INTERNAL_ERROR"
#         message = "server not reachable"
#     elif error_code == 5:
#         award = "INTERNAL_ERROR"
#         message = "file could not saved on praktomat"
#     else:
#         award = "INTERNAL_ERROR"
#         message = "error not specified"
#     return """<loncapagrade>
#     <awarddetail>%s</awarddetail>
#     <message><![CDATA[grade: %s]]></message>
#     <awarded></awarded>
#     </loncapagrade>""" % (award, message)


# def result_page(award, message):
#     return """<loncapagrade>
#     <awarddetail>%s</awarddetail>
#     <message><![CDATA[grade: %s]]></message>
#     <awarded></awarded>
#     </loncapagrade>""" % (award, message)


def authenticate_user(defined_user, request):
    try:
        user = User.objects.get(username__exact=defined_user)  # check if user exist in system
        user.backend = 'django.contrib.auth.backends.ModelBackend'  # prevent error 'User' object
        # has no attribute 'backend'
        login(request, user)
        return True
    except ObjectDoesNotExist:
        return None


# def grade_task(data, request, submitted_file_name, task):
#     #create author_object for submitting data
#     user_id = None
#     author = get_object_or_404(User,
#                                pk=user_id) if user_id else request.user # todo: Ablauf checken vielleicht nur request.user?
#     #get model_solution
#     modelSolution = task.model_solution
#     #add model_solutionpath to submission file
#     #modelSolutionFileObj = SolutionFile.objects.get(pk=task.model_solution_id) # really? create FileObject
#     modelSolutionFileObj = SolutionFile(solution=modelSolution)
#     modelSolutionFilenamePath = modelSolutionFileObj.file.name
#     unwantedPath = "SolutionArchive/Task_" + str(task.id) + "/User_" + str(author.username) + "/Solution_" + \
#                    str(task.model_solution_id) + "/"
#     modelSolutionPath = os.path.dirname(modelSolutionFilenamePath[len(unwantedPath):])
#     submitted_file_name = os.path.join(modelSolutionPath, submitted_file_name)
#     solution = Solution(task=task, author=author)
#     #save the solution model in the database
#     solution.save()
#     #create solution_file
#     solution_file = SolutionFile(solution=solution)
#     #save solution in environment and get the path
#     saved_solution = save_file(data, solution_file, submitted_file_name)
#
#     #remove the upload path /home/ecult/devel_oli/upload
#     shorter_saved_solution = saved_solution[len(settings.UPLOAD_ROOT):]  # todo besser +1 und doku
#     #remove the beginnning slash -> relative path
#     super_short_solution = shorter_saved_solution[1:]
#     #save solution file
#     solution_file.file = super_short_solution
#     solution_file.save()
#     run_all_checker = bool(
#         User.objects.filter(id=user_id, tutorial__tutors__pk=request.user.id) or
#         in_group(request.user, 'Trainer'))  # true show also hidden tests
#     #start the checking process
#     solution.check(run_all_checker)
#     #get result object
#     result = solution.allCheckerResults()
#     return result, solution


# def get_solution(result, result_message, solution):
#     result_message += "<h2>" + "Aufgabe: " + solution.task.title + "</h2>"
#
#     #check for all tests
#     if solution.accepted:
#         result_message += "<p style=\"color:#008500;\">All required tests have been passed.</p>"
#         result_award = "EXACT_ANS"
#     else:
#         result_award = "INCORRECT"
#         result_message += "<p style=\"color:red;\">Not all required tests have been passed.</p>"
#
#     # Details
#     result_message += "<h2>Ergebnisse</h2>"
#     for index in range(len(result)):
#         if result[index].checker.public:
#             result_message += "<h3>" + result[index].checker.title()
#             if result[index].passed:
#                 result_message += " : <span style=\"color:#008500;\"> bestanden</span></h3>"
#             else:
#                 result_message += " : <span style=\"color:red;\"> nicht bestanden</span></h3>"
#
#             result_message += "<div class=\"log\">log: " + result[index].log + "</div>"
#
#     return result_award, result_message


def get_solution_xml(result, solution, file_name, response_format):
    # have to set it manually because it will only check visible tests
    false_required_hidden_test = False
    solution.seperate = True
    grader = dict()
    grader.update({"name": "praktomat"})
    grader.update({"version": version})


    for index in range(len(result)):
        if result[index].checker.required and not result[index].checker.public:
            if not result[index].passed:
                solution.accepted = False
                false_required_hidden_test = True
        logger.debug("Checker: " + str(result[index].checker))

    # remove 'None' tests from proforma2
    res_arr = list(result)
    max = len(res_arr) - 1
    for index in range(len(res_arr)):
        indexReverse = max - index
        if res_arr[indexReverse].checker.proforma_id == "None" and response_format == "proformav2":
            # CopyFile checker has no attribute passed!
            if not res_arr[indexReverse].passed:
            #    # todo if fail add Error-Message
                logger.error('Checker None FAILED!')
            else:
                logger.debug("remove Checker: " + str(res_arr[indexReverse].checker))
                res_arr.remove(res_arr[indexReverse])


    logger.debug("Remaining Checkers: ")
    for index in range(len(res_arr)):
        logger.debug("Checker: " + str(res_arr[index].checker))

    if response_format == "proformav2":
        loncapa_xml = render_to_string('proforma/response_v2.xml',
                           {"solution": solution,
                            "testResultList": res_arr,
                            "fileName": file_name,
                            "grader": grader,
                            "required_hidden": false_required_hidden_test})
    else:
        loncapa_xml = render_to_string('proforma/message.xml',
                           {"solution": solution,
                            "testResultList": result,
                            "fileName": file_name,
                            "required_hidden": false_required_hidden_test})
    return loncapa_xml


# def print_submitted_files(result_message, solution, file_name_string):
#     # print submitted files
#     solutionfiles = solution.solutionfile_set.all()
#     result_message += "<h2>Files</h2>"
#     for index in range(len(solutionfiles)):
#         result_message += "<h3>" + file_name_string + "</h3>"
#         result_message += "<pre>" + solutionfiles[index].content() + "</pre>"
#     return result_message

