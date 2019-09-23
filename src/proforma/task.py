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

# functions for importing ProFormA tasks into Praktomat database

import json
import re

import traceback


from os.path import dirname
from xml.dom import minidom
from xml.dom.minidom import Node

from django.core.exceptions import ObjectDoesNotExist

from django.core.servers.basehttp import FileWrapper
from django.db import models

from django.shortcuts import redirect
from django.template import TemplateSyntaxError
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from django.http import HttpResponse
from lxml import etree
from lxml import objectify
import logging
import zipfile
import tempfile
from os.path import basename

from attestation.models import Rating
from checker import CreateFileChecker, CheckStyleChecker, JUnitChecker, AnonymityChecker, \
    JavaBuilder, DejaGnu, TextNotChecker, PythonChecker, RemoteSQLChecker, TextChecker, SetlXChecker
from checker.models import Checker
from solutions.models import Solution, SolutionFile
from tasks.models import Task, MediaFile
import task_v0_94
import task_v1_01
import task_v2_00


logger = logging.getLogger(__name__)


# def checker_struct(actual_task):
#     checker_classes = filter(lambda x: issubclass(x, Checker), models.get_models())
#     unsorted_checker = sum(map(lambda x: list(x.objects.filter(task=actual_task)), checker_classes), [])
#     checkers_sorted = sorted(unsorted_checker, key=lambda checker: checker.order)
#     rating_scale = actual_task.final_grade_rating_scale
#     media_objects = list(MediaFile.objects.all())
#     model_solution_objects = list(Solution.objects.all())
#     model_solution_file_objects = list(SolutionFile.objects.filter(solution__in=model_solution_objects))
#     return checker_classes, checkers_sorted, media_objects, rating_scale, model_solution_file_objects

def get_storage_path(instance, filename):
        """ Use this function as upload_to parameter for file fields. """
        return 'CheckerFiles/Task_%s/%s/%s' % (instance.task.pk, instance.__class__.__name__, filename)


# @csrf_exempt  # disable csrf-cookie
# def export(request, task_id=None, OutputZip=None):
#     """
#     url:
#     export_task/(?P<task_id>\d{1,6})
#     response: inline or zip
#     """
#
#     # defines which values the praktomat have not in a dict
#     defined = dict()
#     defined["langCode"] = "de"
#     defined["taskLangVersion"] = "1.6"
#     defined["taskLang"] = "java" #TODO: java only if java is the builder
#     defined["JavaVersion"] = "6"
#
#     # check if task exist
#     try:
#         actual_task = Task.objects.get(pk=task_id)
#     except ObjectDoesNotExist:
#         return HttpResponse("Your task: " + task_id + " does not Exist")
#
#     checker_classes, \
#     checkers_sorted, \
#     media_objects, \
#     rating_scale, \
#     model_solution_file_objects = checker_struct(actual_task)
#
#     # fetch files
#     files = []
#     solutionFilesList = []
#     namedFiles = dict()
#     actualSolution = actual_task.model_solution  # todo: only the model-solution not all solutions
#
#     for checker_object in checkers_sorted:
#         file_fields = filter(lambda x: isinstance(x, models.FileField), checker_object.__class__._meta.fields)
#         files += map(lambda file_field: checker_object.__getattribute__(file_field.attname), file_fields)
#
#     for media_object in media_objects:
#         files.append(media_object.media_file)
#
#     for file in files:
#         try:
#             if file.path is None:
#                 pass
#         except Exception as e:
#             return HttpResponse("One of your Checker-Files is empty. Please check the following checker: " + str(file.instance))
#         namedFiles[file] = file.instance.__class__.__name__
#
#     try:
#         solutionFiles = SolutionFile.objects.filter(solution=actualSolution)
#     except Exception as e:
#         return HttpResponse("Error in the solution: " + str(e))
#     for solutionFile in solutionFiles:
#         solutionFilesList.append(solutionFile)
#
#     try:
#         xml = render_to_string('export_external_task/xml_template.xml',
#                                {"defined": defined,
#                                 "task": actual_task,
#                                 "external": OutputZip,
#                                 "files": files,
#                                 "namedFiles": namedFiles,
#                                 "scale": rating_scale,
#                                 "checker": checkers_sorted,
#                                 "modelSolutions": solutionFilesList,
#                                 "checker_classes": checker_classes})
#     except TemplateSyntaxError as e:
#         return HttpResponse("Error in the template: " + str(e), content_type="application/xml")
#
#     xmlFilename = actual_task.title.encode('ascii', errors='replace').strip() + ".xml"
#     xml = xml.encode('utf-8')
#     xml = prettify(xml)
#     fix = re.compile(r'((?<=>)(\n[\t]*)(?=[^<\t]))|(?<=[^>\t])(\n[\t]*)(?=<)')  # todo: prettify lxml
#     prettyXml = re.sub(fix, '', xml)
#
#     if OutputZip:
#         zipName = "".join(actual_task.title.encode('ascii', errors='replace').split()) + ".zip"
#         temp = tempfile.TemporaryFile()
#         archive = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
#         archive.writestr(xmlFilename, prettyXml.encode('utf-8'))
#
#         for fileName in files:
#             archive.write(fileName.path, fileName.name)
#         archive.close()
#         wrapper = FileWrapper(temp)
#
#         response = HttpResponse(wrapper, content_type='application/zip', mimetype="application/x-zip-compressed")
#         response['Content-Disposition'] = 'attachment; filename=' + zipName
#         response['Content-Length'] = temp.tell()
#         temp.seek(0)
#         return response
#     else:
#         # return xml
#         return HttpResponse(prettyXml, content_type="application/xml")
#
#         # return zip
#         #return HttpResponse(response, mimetype="application/x-zip-compressed")
#         #response = HttpResponse(archive, mimetype="application/zip")
#         #response['Content-Disposition'] = 'attachment; filename=TaskExport.zip'


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


# def check_task_id(task_id):
#     """
#     check_task_id(task_id)
#     return task object or None
#     """
#     try:
#         task = Task.objects.get(pk=task_id)
#         return task
#     except ObjectDoesNotExist:
#         return None


# @csrf_exempt  # disable csrf-cookie
# def listTasks(request, ):
#     """
#      url:
#      export_task/list
#      Displays the number of available tasks on the system
#     """
#     response = HttpResponse()
#     allTask = Task.objects.all()
#     response.write("Amount of available tasks: " + str(len(allTask)) + "\r\n")
#
#     for task in allTask:
#         response.write("Task " + str(task.pk) + " title: " + task.title + "\r\n")
#
#     return response


# @csrf_exempt  # disable csrf-cookie
# def activateTasks(request, task_id):
#     """
#      url:
#      export_task/activate
#      set Timer and Grading
#     """
#     response = HttpResponse()
#     try:
#         actual_task = Task.objects.get(pk=task_id)
#     except Exception:
#         response = response.write("Task: " + task_id + " does not exist\r\n Exception: " + str(Exception))
#         return response
#
#     #show task with rating scale and submission date
#     rscaleAll = Rating.objects
#     try:
#         rscale = Rating.objects.get(task=actual_task)
#     except:
#         response = response.write("Rating does not exist")
#         return response
#
#     if rscale:
#         response.write("Title: " + actual_task.title + "\r\n")
#         response.write("Rating Scale: " + str(rscale.aspect) + str(rscale.scale) + "\r\n")
#     else:
#         response.write("No RatingScale")
#     return response


# @csrf_exempt  # disable csrf-cookie
# def detail(request, task_id=None, ):
#     """
#      url:
#      export_task/detail/id
#      Displays some information about the wanted task
#     """
#     try:
#         actual_task = Task.objects.get(pk=task_id)
#     except ObjectDoesNotExist:
#         response = (error_page(1))
#         return response
#
#     response = HttpResponse()
#     response.write("Title: " + actual_task.title + "\n\r")
#     response.write("Details about task: " + str(task_id) + "\n\r")
#     response.write("Publication date: " + str(actual_task.publication_date) + "\n\r")
#     response.write("Submission date: " + str(actual_task.submission_date) + "\n\r")
#     return response


# def error_page(error_code):
#     """
#     error_page(error_code)
#     return (Http-response with Error)
#
#     error_code 1: task does not exist
#     error_code 2: no data is send to script
#     error_code 3: server couldn\'t fulfill the request. (get_data)
#     """
#     response = HttpResponse()
#     if error_code == 0:
#         response.write("Error your Task does not exist")
#     else:
#         response.write("A not defined error occured")
#     return response

#
# def prettify(elem):
#     """Return a pretty-printed XML string for the Element.
#     """
#     # rough_string = ET.tostring(elem, 'utf-8')
#     reparsed = minidom.parseString(elem)
#     remove_blanks(reparsed)
#     return reparsed.toprettyxml(indent='')


# def remove_blanks(node):
#     for x in node.childNodes:
#         if x.nodeType == Node.TEXT_NODE:
#             if x.nodeValue:
#                 x.nodeValue = x.nodeValue.strip()
#         elif x.nodeType == Node.ELEMENT_NODE:
#             remove_blanks(x)


# keep??
# def validation(xmlFile, schemaObject):
#     try:
#         xmlObject = objectify.parse(xmlFile, schemaObject)
#     except etree.XMLSyntaxError, e:
#         print("Your XML is not Valid against the schema.\r\n You got the following error: " + str(e) + "\r\n")
#         return False
#
#     except Exception as e:
#         print ("An unexpected Error occurred! \r\n" + str(e) + "\r\n")
#         return False
#
#     return xmlObject


def check_visibility(inst, namespace, xml_test=None, public=None):
    inst.always = True

    if xml_test is None:
        inst.public = False
        inst.required = False
    else:
        if xml_test.xpath('./p:test-configuration/p:test-meta-data/praktomat:required',
                          namespaces=namespace):
            inst.required = str2bool(xml_test.xpath('./p:test-configuration/'
                                                                                'p:test-meta-data/'
                                                                                'praktomat:required',
                                                                                namespaces=namespace)[0].text)
        if xml_test.xpath('./p:test-configuration/p:test-meta-data/praktomat:public',
                          namespaces=namespace):
            if public is False:
                inst.public = False
            elif public is True:
                inst.public = True
            else:
                inst.public = str2bool(xml_test.xpath('./p:test-configuration/'
                                                                                  'p:test-meta-data/'
                                                                                  'praktomat:public',
                                                                                  namespaces=namespace)[0].text)
    return inst

def testVisibility(inst, xmlTest, namespace, public=None):
    # always is not necessary anymore we want the test everytime
    #if xmlTest.xpath('./test-configuration/test-meta-data/praktomat:always',
    #                 namespaces={'praktomat': 'urn:proforma:praktomat:v0.1'}):
    #    inst.always = str2bool(xmlTest.xpath('./test-configuration/test-meta-data/praktomat:always',
    #                                         namespaces={'praktomat': 'urn:proforma:praktomat:v0.1'})[0].text)
    inst.always = True

    if xmlTest is None:
        inst.public = False
        inst.required = True
    else:
        if xmlTest.xpath('./proforma:test-configuration/proforma:test-meta-data/praktomat:required',
                         namespaces=namespace):
            inst.required = str2bool(xmlTest.xpath('./proforma:test-configuration/'
                                                   'proforma:test-meta-data/'
                                                   'praktomat:required',
                                                   namespaces=namespace)[0].text)
        if xmlTest.xpath('./proforma:test-configuration/proforma:test-meta-data/praktomat:public',
                         namespaces=namespace):
            if public is False:
                inst.public = False
            elif public is True:
                inst.public = True
            else:
                inst.public = str2bool(xmlTest.xpath('./proforma:test-configuration/'
                                                     'proforma:test-meta-data/'
                                                     'praktomat:public',
                                                     namespaces=namespace)[0].text)

    return inst

def creating_file_checker(embedded_file_dict, new_task, ns, val_order, xml_test, required=None):
    order_counter = 1

    for fileref in xml_test.xpath("p:test-configuration/p:filerefs/p:fileref", namespaces=ns):
        if embedded_file_dict.get(fileref.attrib.get("refid")) is not None:
            inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=new_task,
                                                                       order=val_order,
                                                                       path=""
                                                                       )
            inst2.file = embedded_file_dict.get(fileref.attrib.get("refid"))  # check if the refid is there
            if dirname(embedded_file_dict.get(fileref.attrib.get("refid")).name) is not None:
                inst2.path = dirname(embedded_file_dict.get(fileref.attrib.get("refid")).name)
            else:
                pass
            if required is True:
                inst2 = check_visibility(inst=inst2, xml_test=None, namespace=ns, public=True)
            else:
                inst2 = check_visibility(inst=inst2, xml_test=None, namespace=ns, public=False)
            inst2.save()
            order_counter += 1
            val_order += 1  # to push the junit-checker behind create-file checkers
    return val_order




def creatingFileCheckerNoDep(FileDict, newTask, ns, valOrder, xmlTest):
    for fileRef in FileDict.itervalues():
        inst = CreateFileChecker.CreateFileChecker.objects.create(task=newTask,
                                                                  order=valOrder,
                                                                  path=""
                                                                  )
        inst.file = fileRef

        if dirname(fileRef.name) is not None:  # todo: exception if there is an error
            inst.path = dirname(fileRef.name)
        else:
            pass

        inst = testVisibility(inst, xmlTest, ns, False)
        inst.save()
        valOrder += 1
    return valOrder


def reg_check(regText):
    try:
        re.compile(regText)
        is_valid = True
    except re.error:
        is_valid = False
    return is_valid


def extract_zip_with_xml_and_zip_dict(uploaded_file):
    """
    return task task.xml with dict of zip_files
    :param uploaded_file:
    :return:
        task_xml -> the task.xml
        dict_zip_files: dict of the files in the zip
    """
    regex = r'(' + '|'.join([
        r'(^|/)\..*',  # files starting with a dot (unix hidden files)
        r'__MACOSX/.*',
        r'^/.*',  # path starting at the root dir
        r'\.\..*',  # parent folder with '..'
        r'/$',  # don't unpack folders - the zipfile package will create them on demand
        r'META-INF/.*'
    ]) + r')'

    # return task task.xml with dict of zip_files
    # is_zip = True
    # ZIP import
    task_xml = None
    ignored_file_names_re = re.compile(regex)
    zip_file = zipfile.ZipFile(uploaded_file, 'r')
    #zip_file = zipfile.ZipFile(uploaded_file[0], 'r')
    dict_zip_files = dict()
    for zipFileName in zip_file.namelist():
        if not ignored_file_names_re.search(zipFileName):  # unzip only allowed files + wanted file
            zip_file_name_base = basename(zipFileName)
            if zip_file_name_base == "task.xml":
                task_xml = zip_file.open(zipFileName).read()
            else:
                t = tempfile.NamedTemporaryFile(delete=True)
                t.write(zip_file.open(zipFileName).read())  # todo: encoding
                t.flush()
                my_temp = File(t)
                my_temp.name = zipFileName
                dict_zip_files[zipFileName] = my_temp

    if task_xml is None:
        raise Exception("Error: Your uploaded zip does not contain a task.xml.")
    return task_xml, dict_zip_files


def respond_error_message(message):
    response = HttpResponse()
    response.write(message)
    return response

def check_post_request(request):

    postdata = None
    # check request object -> refactor method
    if request.method != 'POST':
        message = "No POST-Request"
        respond_error_message(message=message)
    else:
        try:
            postdata = request.POST.copy()
        except Exception as e:
            message = "Error no Files attached. " + str(e)
            respond_error_message(message=message)

    # it should be one File one xml or one zip
    if len(postdata) > 1:
        message = "Only one file is supported"
        respond_error_message(message=message)
    else:
        pass


# URI entry point
@csrf_exempt  # disable csrf-cookie
def import_task(request):
    """
    :param request: request object for getting POST and GET
    :return: response

    expect xml-file in post-request
    tries to objectify the xml and import it in Praktomat
    """

    logger.debug('import_task 2 called')

    try:
        check_post_request(request)
        filename, uploaded_file = request.FILES.popitem()  # returns list?
        response_data = import_task_internal(filename, uploaded_file[0])
        return HttpResponse(json.dumps(response_data), content_type="application/json")


    except Exception as inst:
        logger.exception(inst)
        print "Exception caught: " + str(type(inst))  # the exception instance
        print "Exception caught: " + str(inst.args)  # arguments stored in .args
        print "Exception caught: " + str(inst)  # __str__ allows args to be printed directly
        callstack = traceback.format_exc()
        print "Exception caught Stack Trace: " + str(callstack)  # __str__ allows args to be printed directly

        #x, y = inst.args
        #print 'x =', x
        #print 'y =', y
        response = HttpResponse()
        response.write("Error while importing task\r\n" + str(inst) + '\r\n' + callstack)


def import_task_internal(filename, task_file):

    logger.debug('import_task_internal called')

    # here is the actual namespace for the version
    format_namespace_v0_9_4 = "urn:proforma:task:v0.9.4"
    format_namespace_v1_0_1 = "urn:proforma:task:v1.0.1"
    format_namespace_v2_0 = "urn:proforma:v2.0"

    rxcoding = re.compile(r"encoding=\"(?P<enc>[\w.-]+)")

    dict_zip_files = None
    if filename[-3:].upper() == 'ZIP':
        task_xml, dict_zip_files = extract_zip_with_xml_and_zip_dict(uploaded_file=task_file)
    else:
        task_xml = task_file[0].read()  # todo check name

    encoding = rxcoding.search(task_xml, re.IGNORECASE)
    if encoding is not None:
        enc = encoding.group('enc')
        if enc.lower() == 'utf-8':
            task_xml = task_xml.decode(enc).encode('utf-8')
        else:
            logger.error('unexpected encoding found: ' + enc)
    xml_object = objectify.fromstring(task_xml)

    #xml_task = xml_object
    # TODO check against schema

    # check Namespace
    if format_namespace_v0_9_4 in xml_object.nsmap.values():
        logger.debug('handle 0.9.4 task')
        response_data = task_v0_94.importTask(task_xml, dict_zip_files)  # request,)
    elif format_namespace_v1_0_1 in xml_object.nsmap.values():
        logger.debug('handle 1.0.1 task')
        response_data = task_v1_01.import_task(task_xml, dict_zip_files)
    elif format_namespace_v2_0 in xml_object.nsmap.values():
        logger.debug('handle 2.0 task')
        response_data = task_v2_00.import_task(task_xml, dict_zip_files)
    else:
        raise Exception("The Exercise could not be imported!\r\nOnly support for the following namespaces: " +
                       format_namespace_v0_9_4 + "\r\n" +
                       format_namespace_v1_0_1 + "\r\n" +
                       format_namespace_v2_0)

    return response_data






