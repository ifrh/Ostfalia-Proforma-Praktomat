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

from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile


from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from django.http import HttpResponse
from lxml import objectify
import logging
import zipfile
import tempfile
from os.path import basename
import hashlib
from tasks.models import Task

from checker.checker import CreateFileChecker
from . import task_v1_01
from . import task_v2_00


logger = logging.getLogger(__name__)


class TaskXmlException(Exception):
    pass

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

def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


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

def creating_file_checker(file_dict, new_task, ns, val_order, xml_test, checker, required=None):
    order_counter = 1

    logger.debug('create file checker for test')
    for fileref in xml_test.xpath("p:test-configuration/p:filerefs/p:fileref", namespaces=ns):
        reffile = file_dict.get(fileref.attrib.get("refid"))
        if reffile is not None:
            logger.debug('create file checker ' + reffile.name)        
            inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=new_task,
                                                                       order=val_order,
                                                                       path=""
                                                                       )
            inst2.file = reffile  # check if the refid is there
            if dirname(reffile.name) is not None:
                inst2.path = dirname(reffile.name)
            if required is True:
                inst2 = check_visibility(inst=inst2, xml_test=None, namespace=ns, public=True)
            else:
                inst2 = check_visibility(inst=inst2, xml_test=None, namespace=ns, public=False)
            inst2.save()
            checker.files.add(inst2)            
            order_counter += 1
            val_order += 1  # to push the junit-checker behind create-file checkers
    return val_order




def creatingFileCheckerNoDep(FileDict, newTask, ns, valOrder, xmlTest):
    for fileRef in FileDict.values():
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

    if type(uploaded_file) == bytes:
        import io
        zip_file = zipfile.ZipFile(io.BytesIO(uploaded_file), "r")
    else:
        zip_file = zipfile.ZipFile(uploaded_file, 'r')


    #zip_file = zipfile.ZipFile(uploaded_file[0], 'r')
    dict_zip_files = dict()
    for zipFileName in zip_file.namelist():
        if not ignored_file_names_re.search(zipFileName):  # unzip only allowed files + wanted file
            zip_file_name_base = basename(zipFileName)
            if zip_file_name_base == "task.xml":
                # binary
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


# def respond_error_message(message):
#     response = HttpResponse()
#     response.write(message)
#     return response

# def check_post_request(request):
#
#     postdata = None
#     # check request object -> refactor method
#     if request.method != 'POST':
#         message = "No POST-Request"
#         respond_error_message(message=message)
#     else:
#         try:
#             postdata = request.POST.copy()
#         except Exception as e:
#             message = "Error no Files attached. " + str(e)
#             respond_error_message(message=message)
#
#     # it should be one File one xml or one zip
#     if len(postdata) > 1:
#         message = "Only one file is supported"
#         respond_error_message(message=message)
#     else:
#         pass


# # URI entry point
# @csrf_exempt  # disable csrf-cookie
# def import_task(request):
#     """
#     :param request: request object for getting POST and GET
#     :return: response
#
#     expect xml-file in post-request
#     tries to objectify the xml and import it in Praktomat
#     """
#
#     logger.debug('import_task 2 called')
#
#     try:
#         check_post_request(request)
#         filename, uploaded_file = request.FILES.popitem()  # returns list?
#         task = import_task_internal(filename, uploaded_file[0])
#         response_data = dict()
#         response_data['taskid'] = task.id
#         response_data['message'] = ''
#         return HttpResponse(json.dumps(response_data), content_type="application/json")
#
#
#     except Exception as inst:
#         logger.exception(inst)
#         print("Exception caught: " + str(type(inst)))  # the exception instance
#         print("Exception caught: " + str(inst.args))  # arguments stored in .args
#         print("Exception caught: " + str(inst))  # __str__ allows args to be printed directly
#         callstack = traceback.format_exc()
#         print("Exception caught Stack Trace: " + str(callstack))  # __str__ allows args to be printed directly
#
#         #x, y = inst.args
#         #print 'x =', x
#         #print 'y =', y
#         response = HttpResponse()
#         response.write("Error while importing task\r\n" + str(inst) + '\r\n' + callstack)


def get_task(hash, uuid, title) :
    #logger.debug('search for' + str(hash) + ' - ' + str(uuid) + ' - ' + title)
    tasks = Task.objects.filter(proformatask_hash = hash).filter(proformatask_uuid = uuid).filter(proformatask_title = title)
    if len(tasks) > 1:
        raise Exception('task with uuid ' + str(uuid) + ' is not unique')
    elif len(tasks) == 1:
        logger.debug('task is stored in database')
        return tasks[0]

    logger.debug('task is not stored in database')
    return None



class Proforma_Task:
    """ Simple class that was created in order to use more generators
    for providing progress information to the user
    """
    def __init__(self):
        self.response_data = None

    def import_task_internal(self, filename, task_file):
        logger.debug('import_task_internal called')

        yield "calculate hash for task file\r\n"
        # here is the actual namespace for the version
        format_namespace_v0_9_4 = "urn:proforma:task:v0.9.4"
        format_namespace_v1_0_1 = "urn:proforma:task:v1.0.1"
        format_namespace_v2_0 = "urn:proforma:v2.0"
        format_namespace_v2_0_1 = "urn:proforma:v2.0.1"

        # rxcoding = re.compile(r"encoding=\"(?P<enc>[\w.-]+)")

        dict_zip_files = None
        if filename[-3:].upper() == 'ZIP':
            if type(task_file) == InMemoryUploadedFile:
                logger.debug('compute MD5 for zip file')
                md5 = hashlib.md5(task_file.read()).hexdigest()
            elif type(task_file) == bytes:
                md5 = hashlib.md5(task_file).hexdigest()
            else:
                logger.debug('class is : ' + task_file.__class__.__name__)
                raise Exception('cannot compute MD5 because of unsupported class')

            task_xml, dict_zip_files = extract_zip_with_xml_and_zip_dict(uploaded_file=task_file)
        else:
            if type(task_file) == InMemoryUploadedFile:
                task_xml = task_file.read()  # todo check name
            else:
                if type(task_file) == TemporaryUploadedFile:
                    task_xml = task_file.read()
                else:
                    task_xml = task_file
            logger.debug('task_xml classname is ' + task_xml.__class__.__name__)
            md5 = hashlib.md5(task_xml).hexdigest()

        logger.debug('task_xml class name is ' + task_xml.__class__.__name__)
        # logger.debug('task_xml = ' + task_xml)
        xml_object = objectify.fromstring(task_xml)
        logger.debug('xml_object class name is ' + xml_object.__class__.__name__)

        # convert MD5 hash to UUID (easier to store in Django)
        import uuid
        hash = uuid.UUID(md5) # as uuid
        logger.debug('task hash is ' + str(hash))

        yield "import\r\n"

        # TODO check against schema??

        # check Namespace
        #if format_namespace_v0_9_4 in list(xml_object.nsmap.values()):
        #    logger.debug('handle 0.9.4 task')
        #    response_data = task_v0_94.importTask(task_xml, dict_zip_files)  # request,)
    #    if format_namespace_v1_0_1 in list(xml_object.nsmap.values()):
    #        logger.debug('handle 1.0.1 task')
    #        response_data = task_v1_01.import_task(task_xml, xml_object, dict_zip_files)
        if format_namespace_v2_0 in list(xml_object.nsmap.values()):
            logger.debug('handle 2.0 task')
            task_2 = task_v2_00.Task_2_00(task_xml, xml_object, hash, dict_zip_files, format_namespace_v2_0)
            yield from task_2.import_task()
            self.response_data = task_2.imported_task
        elif format_namespace_v2_0_1 in list(xml_object.nsmap.values()):
            logger.debug('handle 2.0.1 task')
            task_2 = task_v2_00.Task_2_00(task_xml, xml_object, hash, dict_zip_files, format_namespace_v2_0_1)
            yield from task_2.import_task()
            self.response_data = task_2.imported_task
        else:
            raise Exception("The Exercise could not be imported!\r\nOnly support for the following namespaces: " +
                           # format_namespace_v0_9_4 + "\r\n" +
                           # format_namespace_v1_0_1 + "\r\n" +
                           format_namespace_v2_0)

        if self.response_data == None:
            raise Exception("could not create task")

        # return response_data






