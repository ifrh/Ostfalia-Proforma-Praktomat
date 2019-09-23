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

# this file contains the old REST API used for LON-CAPA in the 'middleware'.
# In this version it is not tested!!
# We keep the code at the moment in case we want to add SVN support which
# is also covered with the old API.


from django.http import HttpResponse

from django.conf import settings
from django.utils.datastructures import MultiValueDictKeyError

#import urllib.parse
#from urlparse import urlparse
import urlparse

import logging

import requests
import os.path
import re
import tempfile
import urllib
import traceback

import svn_submission

logger = logging.getLogger(__name__)

REGEXDOMPATH = re.compile(r"(/uploaded/)+(?P<domain>[a-z0-9]+)(?P<path>[/a-zA-Z.]+)")
REGEXTASKPATH = re.compile(r"(/res/)(?P<domain>[a-z0-9]+)(?P<path>[/a-zA-Z.0-9]+)")

# def save_submission(user_hash, task_uuid, course_hash, submission_url=None, submisssion_fileobj=None, submission_zip=None ):
#     base_dir = os.path.dirname(os.path.dirname(__file__))
#     submission_save_path = os.path.join(base_dir, task_uuid, user_hash, course_hash, )
#     # os.makedirs(base_dir[, mode]) todo save the submission exeption


def answer_format_template(award, message, format=None, awarded=None):
    if format is None or "loncapaV1":
        return """<loncapagrade>
        <awarddetail>%s</awarddetail>
        <message><![CDATA[proforma_taskget: %s]]></message>
        <awarded></awarded>
        </loncapagrade>""" % (award, message)
    else:
        return """<loncapagrade>
        <awarddetail>%s</awarddetail>
        <message><![CDATA[proforma_taskget; %s]]></message>
        <awarded>%s</awarded>
        </loncapagrade>""" % (award, message, awarded)


# OLD API used for LON-CAPA
def grade_api_lon_capa(request, fw=None, fw_version=None):
    """
    main function: coordinates every call
        - gets the submission:
            submission as textfield
            submission as file
            submission as svn-directory
        - gets the
    :param request:
    :param fw:
    :param fw_version:
    :return:
    """

    # Todo add language python;)

    try:
        logger.debug('HTTP_USER_AGENT: ' + request.META.get('HTTP_USER_AGENT') +
                     '\nHTTP_HOST: ' + request.META.get('HTTP_HOST') +
                     '\nrequest.path: ' + request.path +
                     '\nrequest.POST:' + str(list(request.POST.items())))

        # debugging uploaded files
        for f in request.FILES.getlist('file'):
            logger.debug("request.Files: " + str(f))

        if not request.POST:
            raise Exception("No POST-Request attached")

        answer_format_form = request.POST.get("answer-format")
        task_repo = request.POST.get("task-repo")
        submission = request.POST.get("submission")
        exercise_id = request.POST.get("exercise_id")
        task_path = request.POST.get("task-path")
        submission_filename = request.POST.get("submission-filename")
        submission_uri = request.POST.get("submission-uri")
        submission_uri_type = request.POST.get("submission-uri-type")
        external_course_book = request.POST.get("extCoursebook")
        proforma_zip = None
        task_uuid = request.POST.get("uuid")

        ## handling Files
        if request.FILES:
            try:
                if request.FILES['task-file'].name:
                    proforma_zip = dict()
                    proforma_zip[request.FILES['task-file'].name] = request.FILES['task-file']
            except MultiValueDictKeyError:
                # no task-file
                pass

        if not proforma_zip:
            if not task_repo:
                raise Exception("No repository specified")
            if not task_path:
                raise Exception("No task repository to task attached")

        # studip needs an exerciseID -> todo better solution
        if exercise_id:
            task_path = task_path[:-2] + "&exercise_id=" + exercise_id

        if submission:
            if not submission_filename:
                raise Exception("submission_filename is missing")
        elif submission_uri or submission_uri_type:
            if submission_uri_type != "svn-ostfalia":
                if not (submission_uri and submission_uri_type):
                    raise Exception("If you use a submission-uri define type with submission-uri-type: web or svn")
        elif request.FILES['submission-file'].name:
            submission_zip = dict()
            logger.debug("request.FILES['submission-file'].name: " + request.FILES['submission-file'].name)
            submission_zip[request.FILES['submission-file'].name] = request.FILES['submission-file']
        else:
            # logger.error("request.FILES.keys(): " + request.FILES.keys())
            raise Exception("No submission_uri, submission or submissions_file. Please upload only one file")

        # ostfalia
        # SVN-URI = SVN-Server + submission_svn_repository + submission_svn_group
        if submission_uri_type == "svn-ostfalia":
            submission_svn_group, submission_svn_path, submission_svn_repository = svn_submission.get_svn_group(request)
        elif submission_uri_type == "svn":
            if not svn_submission.check_system_svn():
                raise Exception("svn is not installed on the server")
            submission_svn_user = request.POST.get("submission-svn-user")  # could also be a group name
            if not submission_svn_user:
                raise Exception("Please set a submission-svn-user and a submission-svn-revision")

        if external_course_book:
            if settings.EXTCOURSEBOOK.get(external_course_book):
                labor_id = request.POST.get("laborId")
                aufgaben_id = request.POST.get("aufgabenId")
                if not (labor_id and aufgaben_id):
                    raise Exception("If you use an external gradebook add laborId and aufgabenId")
            else:
                raise Exception("Your external Coursebook is not listed added in the middleware")

        # todo: get task from repository or from cache
        # check cache

        # check task-send
        if proforma_zip:
            try:
                for filename, file_obj in proforma_zip.items():
                    task_filename = filename
                    content = file_obj
            except Exception as e:
                raise "read post-request task-file: " + str(type(e))+str(e.args)


        # todo: task_data = check_task(content)
        # todo: 1. check if proglang is supported ->
        # todo: 2. check if checker + version is avail -> send to grader
        # -> chosenGrader
        # create Task and get id
        try:
            if task_path:
                task_filename = os.path.basename(task_path)
            task_id = create_external_task(content_file_obj=content, server=settings.GRADERV, taskFilename=task_filename,
                                           formatVersion=answer_format_form)
        except Exception as e:
            raise Exception("create_external_task: " + str(type(e)) + str(e.args))

        # send student-submission
        if submission:
                return HttpResponse(sendTextfieldPraktomat(studentResponse=submission, studentFilename=submission_filename,
                                                      server=settings.GRADERV, taskID=task_id))
        elif submission_uri or submission_uri_type:
            # todo: allow only allowed domains?
            if submission_uri_type == "web":
                # check structure and content of externalStudentFilePathes
                studentDownloadDomain, studentSubmissionFiles = checkStudentPath(submission_uri)
                # get files from server
                files = getStudentSubmissionFile(filePathList=studentSubmissionFiles, domain=studentDownloadDomain)
                # start grading
                return HttpResponse(send_submission2external_grader(request, settings.JAVAGRADER, task_id, files))
            elif submission_uri_type == "svn-ostfalia":
                grade_result = svn_submission.grade_svn_submission(aufgaben_id, external_course_book, labor_id, request,
                                                    submission_svn_group, submission_svn_path,
                                                    submission_svn_repository, task_id)
                return HttpResponse(grade_result)
            else:
                raise Exception("submission-uri-type is not known")
        elif submission_zip:
            for fname, ffile in request.FILES.items():
                submission_upload_filename = request.FILES[fname].name  # todo: only works with one file and why no chunks?
                uploaded_file_obj = ffile.read()  # take the first element
                uploaded_file = {submission_upload_filename: uploaded_file_obj}
            #uploaded_file_obj = request.FILES[0].read()  # take the first element
            return HttpResponse(send_submission2external_grader(request, settings.GRADERV, task_id, uploaded_file))
        else:
            raise Exception("No submission nor submission-uri is set")

    except Exception as inst:
        logger.exception(inst)
        callstack = traceback.format_exc()
        print "Exception caught Stack Trace: " + str(callstack)  # __str__ allows args to be printed directly
        response = HttpResponse()
        response.write(answer_format_template(award="ERROR", message="Error in grading process: " + str(inst) + callstack))
        #response.write(api_v2.get_http_error_page('Error in grading process', str(inst), callstack))
        response.status_code = 500 # internal error
        return response







def sendTextfieldPraktomat(studentResponse, studentFilename, server, taskID):
    post_data = [("LONCAPA_student_response", studentResponse), ]
    payload = {'LONCAPA_student_response': studentResponse}
    # ToDo : simplify URI for grading
    serverpath = urllib.parse.urlparse(server)  # todo trailing slashes
    if settings.OUTPUTXML:
        domainnOutput = "textfield/lcxml"
    else:
        domainnOutput = "textfield/LC_2.10.1"
    path = "/".join([str(x).rstrip('/') for x in [serverpath.path, domainnOutput,
                                                       str(studentFilename), str(taskID)]])
    grading_url = urllib.parse.urljoin(server, path)
    result = requests.post(url=grading_url, data=payload)

    if result.status_code == requests.codes.ok:
        return result.text

    raise Exception(result.text)


def send_submission2external_grader(request, server, taskID, files):
    serverpath = urllib.parse.urlparse(server)
    domainOutput = "external_grade/proforma/v1/task/"
    path = "/".join([str(x).rstrip('/') for x in [serverpath.path, domainOutput, str(taskID)]])
    gradingURL = urllib.parse.urljoin(server, path)
    result = requests.post(url=gradingURL, files=files)
    if result.status_code == requests.codes.ok:
        return result.text

    raise Exception(result.text)


def create_external_task(content_file_obj, server, taskFilename, formatVersion):

    #if settings.server.get(server):
    #    LOGINBYSERVER
    FILENAME = taskFilename
    #f = codecs.open(content_file_obj.name, 'r+', 'utf-8')
    #files = {FILENAME: codecs.open(content_file_obj.name, 'r+', 'utf-8')}

    try:
        files = {FILENAME: open(content_file_obj.name, 'rb')}
    except IOError:  #
        files = {FILENAME: content_file_obj}
    url = urllib.parse.urljoin(server, 'importTaskObject/V1.01')
    result = requests.post(url, files=files)

    if result.headers['Content-Type'] == 'application/json':
        taskid = result.json().get('taskid')
        return taskid
    else:
        raise IOError("Error while creating task on grader " + result.text)




def checkStudentPath(filePathes):
    # /uploaded/fhwfdev4/OliR/portfolio/HelloWorld.java split it
    splittedFilePathes = filePathes.split(',')
    splittedFilePathes = [_f for _f in splittedFilePathes if _f]  # remove empty list elements
    domain = None
    filePathList = []
    for path in splittedFilePathes:
        match = re.search(REGEXDOMPATH, path)
        if match:
            if domain is None:
                submissionDomain = match.group('domain')
                if settings.LONCAPA_DOMAINS.get(submissionDomain):
                    submissionDomain = settings.LONCAPA_DOMAINS.get(submissionDomain)
                else:
                    raise ImportError('Could not download task student submission file. Your student submission path '
                                      'is not correct /uploaded/{domain}/{path}')
            if match.group('path'):
                filePathList.append(match.group('path'))
            else:
                message = "The path to your submission is not correct: " + str(path)
                raise ImportError(message)
        else:
            raise ImportError('Could not download task student submission file. Your student submission path '
                              'is not correct /uploaded/{domain}/{path}')
    return submissionDomain, filePathList


def getStudentSubmissionFile(filePathList, domain):
    listOfSolutionFiles = []
    with requests.Session() as s:
        for filePath in filePathList:
            url = domain + '/uploaded/' + filePath
            # todo:parallel downloads? http://docs.python-requests.org/en/v0.10.6/user/advanced/#asynchronous-requests
            try:
                req_get = requests.Request(method='GET', url=url)
                prepped = s.prepare_request(req_get)
                response = s.send(prepped, verify=False)

                if response.status_code != 200:
                    message = "Could not download submission file from server: " + url
                    raise IOError(message)
                else:
                    try:
                        with tempfile.NamedTemporaryFile(delete=False) as submissionFile:
                            listOfSolutionFiles.append(submissionFile.write(response.content))
                    except Exception:
                        raise Exception("Error while saving submission file in tempfile")

            except Exception:
                raise Exception("An Error occured while downloading studentsubmission")
    return listOfSolutionFiles


# @csrf_exempt
# def get_version(request):
#     contents = ""
#     try:
#         with open("VERSION", "r") as f:
#             contents = f.read()
#     except Exception:
#         return HttpResponse("Could not read version")
#     return HttpResponse(contents)
