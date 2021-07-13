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
import traceback

from lxml import etree



from django.http import HttpResponse
from django.utils.datastructures import MultiValueDictKeyError
from django.core.files import File

import os
import re
import logging
from . import task
from . import grade
import VERSION
import zipfile
import tempfile



BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARENT_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
logger = logging.getLogger(__name__)

# NAMESPACES = {'dns': 'urn:proforma:v2.0'}
NAMESPACES_V2_0 = 'urn:proforma:v2.0'
NAMESPACES_V2_1 = 'urn:proforma:v2.1'


# string format for exception return message in HTTP
def get_http_error_page(title, message, callstack):
    return """%s

    %s

Praktomat: %s

Callstack:
    %s""" % (title, message, VERSION.version, callstack)


# exception class for handling situations where
# the submission cannot be found from external resource
class ExternalSubmissionException(Exception):
    pass

# wrapper class for handling submissions already stored on disk
class PhysicalFile:
    def __init__(self, path):
        self.path = path


# class for storing information about source control
class VersionControlSystem:
    def __init__(self, revision, uri):
        self.system = 'SVN'
        self.revision = revision
        self.uri = uri

def grade_api_v2(request,):
    """
    grade_api_v2
    rtype: grade_api_v2
    """

    logger.debug("new grading request")

    xml_version = None
    answer_format = "proformav2"

    # create task and get Id
    try:
        # get request XML from LMS (called 'submission.xml' in ProFormA)
        xml = get_request_xml(request)
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
        # print ('NAMESPACE ' + root.xpath('namespace-uri(.)'))
        # print (root.nsmap[None])
        # NAMESPACES = {'dns': root.nsmap[None]}
        NAMESPACE = None
        for key, value in root.nsmap.items():
            if key == None:
                if value == NAMESPACES_V2_0:
                    NAMESPACE = NAMESPACES_V2_0
                    templatefile = 'proforma/response_v2.0.xml'
                elif value == NAMESPACES_V2_1:
                    NAMESPACE = NAMESPACES_V2_1
                    templatefile = 'proforma/response_v2.1.xml'
                else:
                    raise Exception("do not support namespace " + value)

        NAMESPACES = {'dns': NAMESPACE}



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

        # xml2dict is very slow
        #submission_dict = xml2dict(xml)

        logger.info("grading request for task " + task_filename)

        submission_files, version_control = get_submission_files(root, request, NAMESPACES) # returns a dictionary (filename -> content)
        logger.debug('import task')
        proformatask = task.import_task_internal(task_filename, task_file)

        # run tests
        grader = grade.Grader(proformatask, NAMESPACE)
        grader.grade(submission_files, version_control, True)
        # get result
        grade_result = grader.get_result(templatefile)

        # return result
        logger.debug("grading finished")
        logger.debug("--------------------")
        response = HttpResponse()
        response.write(grade_result)
        response.status_code = 200
        return response

    except ExternalSubmissionException as inst:
        logger.exception(inst)
        callstack = traceback.format_exc()
        print("ExternalSubmissionException caught Stack Trace: " + str(callstack))
        response = HttpResponse()
        response.write(get_http_error_page('Could not get submission files', str(inst), callstack))
        response.status_code = 404 # file not found
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


def get_request_xml(request):
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
                xml = request.FILES['submission.xml'].read() # convert InMemoryUploadedFile to string
                return xml
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



def get_submission_file_from_request(searched_file_name, request):
    # remove beginning and trailing whitespaces
    searched_file_name = searched_file_name.strip()

    logger.debug("search submission file: '" + searched_file_name + "'")

    for filename, file in list(request.FILES.items()):
        name = request.FILES[filename].name
        logger.debug("request.FILES['" + filename + "'].name = '" + name + "'")

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

    raise Exception("could not find external submission " + searched_file_name)



def get_submission_files(root, request, NAMESPACES):
    ## TODO: read binary if possible and write binary without conversion

    # check for external submission
    submission_element = root.find(".//dns:external-submission", NAMESPACES)
    if submission_element is not None:
        # handle external submission
        submission_uri = submission_element.text
        if not submission_uri:
            raise Exception("invalid value for external-submission (none)")

        # extract filename (list)
        m = re.match(r"(http\-file\:)(?P<file_name>.+)", submission_uri)
        if m:
            logger.debug('submission attached to request')
            # special case for attached submission
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
            return submission_files_dict, None
        else:
            # expect actual URI
            # SVN:
            # export submission from URI
            logger.debug('SVN submission')
            return get_submission_files_from_svn(submission_uri, NAMESPACES)


    #embedded submission
    logger.debug('embedded submission')
    return get_submission_files_from_submission_xml(root, NAMESPACES)


def get_submission_files_from_submission_xml(root, NAMESPACES):
    submission_files_dict = dict()
    # handle embedded text files
    submission_elements = root.findall(".//dns:files/dns:file/dns:embedded-txt-file", NAMESPACES)
    for sub_file in submission_elements:
        # logger.debug(sub_file)
        filename = sub_file.attrib["filename"]
        # logger.debug('classname is ' + sub_file.text.__class__.__name__)
        file_content = sub_file.text  # no need to encode because it is already a Unicode object
        submission_files_dict.update({filename: file_content})

    # handle embedded binary base64 encoded files
    submission_elements = root.findall(".//dns:files/dns:file/dns:embedded-bin-file", NAMESPACES)
    for sub_file in submission_elements:
        filename = sub_file.attrib["filename"]
        import base64
        file_content = base64.b64decode(sub_file.text)
        submission_files_dict.update({filename: file_content})

    submission_elements = root.findall(".//dns:files/dns:file/dns:attached-bin-file", NAMESPACES)
    if len(submission_elements) > 0:
        raise Exception("attached-bin-file in submission is not supported")
    submission_elements = root.findall(".//dns:files/dns:file/dns:attached-txt-file", NAMESPACES)
    if len(submission_elements) > 0:
        raise Exception("attached-txt-file in submission is not supported")
    if len(submission_files_dict) == 0:
        raise Exception("No submission attached")
    return submission_files_dict, None


def get_submission_files_from_svn(submission_uri, NAMESPACES):
    from utilities.safeexec import execute_arglist
    from django.conf import settings

    folder = tempfile.mkdtemp()
    tmp_dir = os.path.join(folder, "submission")
    cmd = ['svn', 'export', '--username', os.environ['SVNUSER'], '--password', os.environ['SVNPASS'], submission_uri,
           tmp_dir]
    # logger.debug(cmd)
    # fileseeklimit: do not limit here!
    [output, error, exitcode, timed_out, oom_ed] = \
        execute_arglist(cmd, folder, environment_variables={}, timeout=settings.TEST_TIMEOUT,
                        fileseeklimit=None,  # settings.TEST_MAXFILESIZE,
                        extradirs=[], unsafe=True)

    if exitcode != 0:
        message = ''
        if error != None:
            logger.debug('error: ' + str(error))
            message += error + ' '
        if output != None:
            logger.debug('output: ' + str(output))
            message += output
        raise ExternalSubmissionException(message)
    if timed_out:
        raise ExternalSubmissionException('timeout when getting svn submission')

    # logger.debug('SVN-output: ' + output)
    # find revision
    m = re.search(r"(Exported revision )(?P<revision>.+)\.", output)
    revision = 'unknown revision'
    if m:
        if m.group('revision') is not None:
            revision = m.group('revision')
        logger.debug("SVN revision is: " + revision)

    versioncontrolinfo = VersionControlSystem(revision, submission_uri)

    # create filename dictionary
    submission_files_dict = dict()
    import glob
    for file_name in glob.iglob(tmp_dir + '/**/*', recursive=True):
        if not os.path.isfile(file_name):  # ignore directories
            continue

        shortname = file_name[len(tmp_dir) + 1:]
        # logger.debug('add ' + str(shortname))
        submission_files_dict[shortname] = PhysicalFile(file_name)
    return submission_files_dict, versioncontrolinfo


