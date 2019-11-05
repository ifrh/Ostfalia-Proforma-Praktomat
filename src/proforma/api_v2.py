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
# ProFormA-interface V 2.0



#import tempfile
#from urllib.parse import urlparse # version 3
#import urlparse
import traceback

from lxml import etree



from django.http import HttpResponse
from django.utils.datastructures import MultiValueDictKeyError
from django.core.files import File
#from django.views.decorators.csrf import csrf_exempt
#from django.conf import settings

import os
import re
#import shutil
import logging
#import xmlschema
#from requests.exceptions import InvalidSchema
from . import task
from . import grade
import zipfile
import tempfile
import VERSION

#from proforma_taskget.views import login_phantomjs, get_task_from_externtal_server, answer_format_template

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARENT_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
logger = logging.getLogger(__name__)

NAMESPACES = {'dns': 'urn:proforma:v2.0'}

def get_http_error_page(title, message, callstack):
    return """%s

    %s

Praktomat: %s

Callstack:
    %s""" % (title, message, VERSION.version, callstack)




def grade_api_v2(request,):
    """
    grade_api_v2
    rtype: grade_api_v2
    """

    logger.debug("new grading request")

    xml_version = None
    answer_format = "proformav2"

#    logger.debug('HTTP_USER_AGENT: ' + request.META.get('HTTP_USER_AGENT') +
#                 '\nHTTP_HOST: ' + request.META.get('HTTP_HOST') +
#                 '\nrequest.path: ' + request.path +
#     '\nrequest.POST:' + str(list(request.POST.items())))

    # create task and get Id
    try:
        # check request
        xml = get_submission_xml(request)
        logger.debug("type(xml): " + str(type(xml)))
        #logger.debug("got xml: " + xml)

        # debugging uploaded files
        #for field_name, file in request.FILES.items():
        #    filename = file.name
        #    logger.debug("grade_api_v2: request.Files: " + str(file) + "\tfilename: " + str(filename))

        # todo:
        # 1. check xml -> validate against xsd
        # 2. check uuid or download external xml
        # 3. files > file id all should be zipped


        # get xml version
        #xml_version = get_xml_version(submission_xml=xml)

        # do not validate for performance reasons
        # validate xsd
        #if xml_version:
        #    # logger.debug("xml: " + xml)
        #    is_valid = validate_xml(xml=xml, xml_version=xml_version)
        #else:
        #    logger.debug("no version - " + str(xml))
        #    is_valid = validate_xml(xml=xml)

        #logger.debug(xml)

        # note: we use lxml/etree here because it is very fast
        root = etree.fromstring(xml)

        task_file = None
        task_filename = None
        task_element = root.find(".//dns:external-task", NAMESPACES)
        if task_element is not None:
            task_file, task_filename = get_external_task(request, task_element.text)
            #logger.debug('external-task in ' + task_path)
        else:
            task_element = root.find(".//dns:task", NAMESPACES)
            if task_element is not None:
                raise Exception ("embedded task in submission.xml is not supported")
            else:
                task_element = root.find(".//dns:inline-task-zip", NAMESPACES)
                if task_element is not None:
                    raise Exception ("inline-task-zip in submission.xml is not supported")
                else:
                    raise Exception("could not find task in submission.xml")
        #logger.debug("got task")


        # xml2dict is very slow
        #submission_dict = xml2dict(xml)
        #logger.debug("xml->dict")

        # task_type_dict = check_task_type(submission_dict)
        submission_files = get_submission_files(root, request) # returns a dictionary (filename -> contant)

        logger.info("grading request for task " + task_filename)
        logger.debug('import task')
        response_data = task.import_task_internal(task_filename, task_file)
        #print 'result for Task-ID: ' + str(response_data)
        task_id = str(response_data['taskid'])
        message = response_data['message']
        if task_id == None:
            raise Exception("could not create task")

        # send submission to grader
        logger.debug('grade submission')
        grade_result = grade.grader_internal(task_id, submission_files, answer_format)
        #grade_result = grader_internal(task_id, submission_zip, answer_format)

        # handle situation with German characters in output (e.g. from student code)
        # grade_result = grade_result.encode('utf-8').decode('latin-1')

        logger.debug("grading finished")
        response = HttpResponse()
        response.write(grade_result)
        response.status_code = 200
        return response

    except Exception as inst:
        logger.exception(inst)
        callstack = traceback.format_exc()
        print("Exception caught Stack Trace: " + str(callstack))  # __str__ allows args to be printed directly
        response = HttpResponse()
        response.write(get_http_error_page('Error in grading process', str(inst), callstack))
        response.status_code = 500 # internal error
        return response


def get_external_task(request, task_uri):

    # logger.debug("task_uri: " + str(task_uri))
    ##
    # test file-field
    m = re.match(r"(http\-file\:)(?P<file_name>.+)", task_uri)
    file_name = None
    if m:
        file_name = m.group('file_name')
    else:
        raise Exception("uunsupported external task URI: " + task_uri)

    logger.debug("file_name: " + str(file_name))
    for filename, file in list(request.FILES.items()):
        name = request.FILES[filename].name
        if name == file_name:
            task_filename = name
            task_file = file
            return task_file, task_filename

    raise Exception("could not find task with URI " + task_uri)




def get_submission_xml(request):
    """
    check the POST-Object
    1. could be just a submission.xml
    2. could be a submission.zip

    :rtype: submission.xml
    :param request: 
    """
    # todo check encoding of the xml -> first line
    encoding = 'utf-8'
    if not request.POST:

        #if not request.FILES:
        #    raise KeyError("No submission attached")

        try:
            # submission.xml in request.Files
            logger.debug("FILES.keys(): " + str(list(request.FILES.keys())))
            if request.FILES['submission.xml'].name is not None:
                #xml_dict = dict()
                #xml_dict[request.FILES['submission.xml'].name] = request.FILES['submission.xml']
                #logger.debug("xml_dict.keys(): " + str(xml_dict.keys()))
                #xml = xml_dict.popitem()[1].read()
                #xml_decoded = xml.decode(encoding)
                xml = request.FILES['submission.xml'].read() # convert InMemoryUploadedFile to string
                #xml_encoded = xml.encode(encoding)
                return xml # xml_encoded
            elif request.FILES['submission.zip'].name:
                # todo zip handling -> praktomat zip
                raise Exception("zip handling is not implemented")
            else:
                raise KeyError("No submission attached")
        except MultiValueDictKeyError:
            raise KeyError("No submission attached")
    else:
        logger.debug("got submission.xml as form data")
        xml = request.POST.get("submission.xml")

        # logger.debug('submission' + xml)
        if xml is None:
            raise KeyError("No submission attached -> submission.xml")

        xml_encoded = xml.encode(encoding)
        return xml_encoded




# def response_error(msg, format):
#     """
#
#     :param msg:
#     :return: response
#     """
#     return HttpResponse(answer_format("error", msg, format))


# def get_xml_version(submission_xml):
#     pass  # todo check namespace for version
#     return "proforma_v2.0"


# def validate_xml(xml, xml_version=None):
#     logger.debug("xml_version: " + xml_version)
#     if xml_version is None:
#         logger.debug("PARENT_BASE_DIR: " + PARENT_BASE_DIR)
#         schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, 'xsd/proforma_v2.0.xsd'))
#         try:
#             schema.validate(xml)
#         except Exception as e:
#             logger.error("Schema is not valid: " + str(e))
#             raise Exception("Schema is not valid: " + str(e))
#     else:
#         if settings.PROFORMA_SCHEMA.get(xml_version):
#             logger.debug("try and validate xsd file: " + os.path.join(PARENT_BASE_DIR, settings.PROFORMA_SCHEMA.get(xml_version)))
#             schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, settings.PROFORMA_SCHEMA.get(xml_version)))
#             try:
#                 schema.validate(xml)
#             except Exception as e:
#                 logger.error("Schema is not valid: " + str(e))
#                 raise Exception("Schema is not valid: " + str(e))
#         else:
#             logger.exception("validate_xml: schema ist not supported")
#             raise Exception("schema ist not supported")
#
#     logger.debug("XML schema validation succeeded")
#
#     return True


# expensive (i.e. time consuming operation)
# def xml2dict(xml):
#     schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, 'xsd/proforma_v2.0.xsd'))  # todo fix this
#     xml_dict = xmlschema.to_dict(xml_document=xml, schema=schema)
#     return xml_dict


# def check_task_type(submission_dict):
#     if submission_dict.get("external-task"):
#         task_path = submission_dict["external-task"]["$"]
#         task_uuid = submission_dict["external-task"]["@uuid"]
#         return {"external-task": {"task_path": task_path, "task_uuid": task_uuid}}
#     elif submission_dict.get("task"):
#         return "task"
#     elif submission_dict.get("inline-task-zip"):
#         return "inline-task-zip"
#     else:
#         return None







def get_submission_file_from_request(searched_file_name, request):

    logger.debug("search submission file: " + searched_file_name)

    for filename, file in list(request.FILES.items()):
        name = request.FILES[filename].name
        logger.debug("request.FILES[" + filename + "].name = " + name)

        if filename == searched_file_name:
            submission_files_dict = dict()
            if name.lower().endswith('.zip'):
                # uncompress submission
                regex = r'(' + '|'.join([
                    r'/$',  # don't unpack folders - the zipfile package will create them on demand
                ]) + r')'
                ignored_file_names_re = re.compile(regex)

                zip_file = zipfile.ZipFile(file, 'r')
                for zipFileName in zip_file.namelist():
                    if not ignored_file_names_re.search(zipFileName):  # unzip only allowed files + wanted file
                        t = tempfile.NamedTemporaryFile(delete=True)
                        t.write(zip_file.open(zipFileName).read())  # todo: encoding
                        t.flush()
                        my_temp = File(t)
                        my_temp.name = zipFileName
                        submission_files_dict[zipFileName] = my_temp

                return submission_files_dict

            elif name.lower().endswith('.jar'):
                # read binary file
                logger.debug("submission file is a JAR file")
                file_content = str(file.read())
                submission_files_dict.update({searched_file_name: file_content})
                return submission_files_dict
            # elif name.lower().endswith('.java'):
            #     # special handling for single java files
            #     # add package name to filename
            #     # TODO: move to grader
            #     logger.debug("SPECIAL HANDLING FOR JAVA FILE")
            #     logger.debug('File class is ' + file.__class__.__name__)
            #     file.close()
            #     file.open() # open in text mode
            #     file_content = file.read()
            #
            #     short_filename = os.path.basename(searched_file_name)
            #     if short_filename == searched_file_name: # short filename
            #         package = grade.find_java_package_path(file_content)
            #         logger.debug('classname is ' + file_content.__class__.__name__)
            #         if len(package) > 0:
            #             short_filename =  package + '/' + searched_file_name
            #         else:
            #             short_filename = searched_file_name
            #         submission_files_dict.update({short_filename: file_content})
            #     else:
            #         submission_files_dict.update({searched_file_name: file_content})
            #
            #     return submission_files_dict
            else:
                file_content = file.read() ##.decode('utf-8')
                submission_files_dict.update({searched_file_name: file_content})
                return submission_files_dict


    # logger.debug("not found => relative path?: " + searched_file_name)
    #
    # # special handling for filenames containing a relative path (Java):
    # # if file_name is not found:
    # for filename, file in request.FILES.items():
    #     # name = request.FILES[filename].name
    #     # logger.debug("request.FILES[" + name + "]")
    #     pure_filename = os.path.basename(searched_file_name)  # remove path
    #     if filename == pure_filename:
    #         submission_files_dict = dict()
    #         file_content = file.read().decode('utf-8')
    #         submission_files_dict.update({searched_file_name: file_content})
    #         return submission_files_dict

    raise Exception("could not find external submission " + searched_file_name)

def get_submission_files(root, request):
    ## TODO: read binary if possible and write binary without conversion

    submission_element = root.find(".//dns:external-submission", NAMESPACES)
    if submission_element is not None:
        # handle external submission
        field_name = submission_element.text
        if not field_name:
            raise Exception("invalid value for external-submission (none)")

        # extract filename (list)
        m = re.match(r"(http\-file\:)(?P<file_name>.+)", field_name)
        if not m:
            raise Exception("unsupported external-submission: " + field_name)
        file_names = m.group('file_name')
        if file_names is None:
            raise Exception("missing filename in external-submission")

        logger.debug("submission filename(s): " + str(file_names))
        # filename may be a list of filenames
        names = str(file_names).split(',')
        submission_files_dict = dict()
        for searched_file_name in names:
            # collect all files
            submission_files_dict.update(get_submission_file_from_request(searched_file_name, request))
        return submission_files_dict

    submission_files_dict = dict()
    submission_elements = root.findall(".//dns:files/dns:file/dns:embedded-txt-file", NAMESPACES)
    for sub_file in submission_elements:
        #logger.debug(sub_file)
        filename = sub_file.attrib["filename"]
        #logger.debug('classname is ' + sub_file.text.__class__.__name__)
        file_content = sub_file.text  # no need to encode because it is already a Unicode object
        submission_files_dict.update({filename: file_content})

    submission_elements = root.findall(".//dns:files/dns:file/dns:embedded-bin-file", NAMESPACES)
    if len(submission_elements) > 0:
        raise Exception("embedded-bin-file in submission is not supported")
    submission_elements = root.findall(".//dns:files/dns:file/dns:attached-bin-file", NAMESPACES)
    if len(submission_elements) > 0:
        raise Exception("attached-bin-file in submission is not supported")
    submission_elements = root.findall(".//dns:files/dns:file/dns:attached-txt-file", NAMESPACES)
    if len(submission_elements) > 0:
        raise Exception("attached-txt-file in submission is not supported")

    if len(submission_files_dict) == 0:
        raise Exception("No submission attached")

    return submission_files_dict

# compress file dictionary as zip file
# def file_dict2zip(file_dict):
#     tmp_dir = tempfile.mkdtemp()
#
#     try:
#
#         os.chdir(os.path.dirname(tmp_dir))
#         for key in file_dict:
#             logger.debug("file_dict2zip Key: " + key)
#             if os.path.dirname(key) == '':
#                 with open(os.path.join(tmp_dir, key), 'w') as f:
#                     f.write(file_dict[key])
#             else:
#                 if not os.path.exists(os.path.join(tmp_dir, os.path.dirname(key))):
#                     os.makedirs(os.path.join(tmp_dir, os.path.dirname(key)))
#                 with open(os.path.join(tmp_dir, key), 'w') as f:
#                     f.write(file_dict[key])
#
#         submission_zip = shutil.make_archive(base_name="submission", format="zip", root_dir=tmp_dir)
#         submission_zip_fileobj = open(submission_zip, 'rb')
#         return submission_zip_fileobj
#     except IOError as e:
#         raise IOError("IOError:", "An error occurred while open zip-file", e)
#     #except Exception as e:
#     #    raise Exception("zip-creation error:", "An error occurred while creating zip: E125001: "
#     #                    "Couldn't determine absolute path of '.'", e)
#     finally:
#         shutil.rmtree(tmp_dir)


# def create_external_task(content_file_obj, server, taskFilename, formatVersion):
#
#
#
#     #if settings.server.get(server):
#     #    LOGINBYSERVER
#     FILENAME = taskFilename
#     #f = codecs.open(content_file_obj.name, 'r+', 'utf-8')
#     #files = {FILENAME: codecs.open(content_file_obj.name, 'r+', 'utf-8')}
#
#     try:
#         files = {FILENAME: open(content_file_obj.name, 'rb')}
#     except IOError:  #
#         files = {FILENAME: content_file_obj}
#     url = urlparse.urljoin(server, 'importTask')
# #    url = urllib.parse.urljoin(server, 'importTask')
#     result = requests.post(url, files=files)
#
#     message = ''
#     if result.headers['Content-Type'] == 'application/json':
#         logger.debug(result.text)
#         #try:
#         taskid = result.json().get('taskid')
#         message = result.json().get('message')
#
#         #except ValueError:
#         #    message = "Error while creating task on grader: " + str(ValueError)
#         #    raise ValueError(message)
#         #except Exception:
#         #    message = "Error while creating task on grader: " + str(Exception)
#         #    raise Exception(message)
#     else:
#         message = "Could not create task on grader: " + result.text
#         raise IOError(message)
#
#     if taskid == None:
#         logger.debug('could not create task: ' + str(message))
#         raise Exception('could not create task: ' + str(message))
#
#     return taskid


# def send_submission2external_grader(request, server, taskID, files, answer_format):
#     logger.debug("send_submission2external_grader called")
#     serverpath = urlparse.urlparse(server)#
# ##    serverpath = urllib.parse.urlparse(server)
#     domainOutput = "external_grade/" + str(answer_format) + "/v1/task/"
#     path = "/".join([str(x).rstrip('/') for x in [serverpath.path, domainOutput, str(taskID)]])
#     gradingURL = urlparse.urljoin(server, path)
# ##    gradingURL = urllib.parse.urljoin(server, path)
#     logger.debug("gradingURL: " + gradingURL)
#     result = requests.post(url=gradingURL, files=files)
#     return result
#     #if result.status_code == requests.codes.ok:
#     #    return result.text
#     #else:
#     #    logger.exception("send_submission2external_grader: " + str(result.status_code) + "result_text: " + result.text)
#     #    raise Exception(result.text)