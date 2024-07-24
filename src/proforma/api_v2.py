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



from django.http import HttpResponse, StreamingHttpResponse
from django.utils.datastructures import MultiValueDictKeyError
from django.core.files import File
from django.template.loader import render_to_string

# from solutions.models import Solution


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

%s""" % (title, message, VERSION.version, callstack)


# exception class for handling situations where
# the submission cannot be found from external resource
class ExternalSubmissionException(Exception):
    pass
#    def __init__(self, message):
#        self.message = message
#        super(ExternalSubmissionException, self).__init__(message)

# wrapper class for handling submissions already stored on disk
class PhysicalFile:
    def __init__(self, path):
        self.path = path


# class for storing information about source control
class VersionControlSystem:
    def __init__(self, vcstype, uri, revision=None):
        self.system = vcstype
        self.uri = uri
        self.revision = revision

class Subversion(VersionControlSystem):
    def __init__(self, uri, revision):
        super().__init__('SVN', uri, revision)

class Git(VersionControlSystem):
    def __init__(self, uri, commit):
        super().__init__('Git', uri, commit)



def upload_v2(request,):
    """
    upload_v2
    rtype: upload_v2
    """

    logger.debug("new upload request")

    try:
        proformarequest = Proforma_Request(request)
        response = StreamingHttpResponse(proformarequest.import_task_yield_exc())
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
    except Exception as inst:
        logger.exception(inst)
#        response = HttpResponse()
#        callstack = traceback.format_exc()
#        response.write(get_http_error_page('Upload task error', str(inst), callstack))
#        response.status_code = 500 # internal server error
#        return response

def runtest(request,):
    """
    like grade_api_v2 but with server sent events
    """
    logger.debug("new request for running tests")

    try:
        proformarequest = Proforma_Request(request)
        response = StreamingHttpResponse(proformarequest.run_test_yield_exc())
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
    except Exception as inst:
        logger.exception(inst)

def grade_api_v2(request,):
    """
    grade_api_v2
    rtype: grade_api_v2
    """

    logger.debug("new grading request")

    # create task and get Id
    try:
        proformatask = Proforma_Request(request)
        a = proformatask.import_task()
        # 'consume' a, needed because import_task is a generator which returns an iterator
        # This is required, otherwise the function is not completely executed
        b = list(a)
        #        logger.debug("Number of solutions: " + str(Solution.objects.filter(task=proformatask).count()))

        grader = grade.Grader(proformatask.proformatask, proformatask.NAMESPACE)
        logger.debug(proformatask.NAMESPACES)
        submission_files, version_control = proformatask.get_submission_files() # returns a dictionary (filename -> content)

        # run tests
        a = grader.grade(submission_files, version_control, True)
        # once again: consume
        b = list(a)

        # get result
        grade_result = grader.get_result(proformatask.templatefile)

        # return result
        logger.debug("grading finished")
        logger.debug("--------------------")
        response = HttpResponse()
        response.write(grade_result)
        response.status_code = 200
#        logger.debug("Number of solutions: " + str(Solution.objects.filter(task=proformatask).count()))
        return response

    except ExternalSubmissionException as inst:
        import sys
        ex_type, ex_value, ex_traceback = sys.exc_info()

        print(inst)
        logger.exception(inst)
        callstack = traceback.format_exc()
        print("ExternalSubmissionException caught Stack Trace: " + str(callstack))
        response = HttpResponse()
        from datetime import datetime
        now = datetime.now().isoformat()

        response_xml = render_to_string("proforma/response_student_visible_error.xml",
                           {
                            "title" : "External submission error",
                            "error": str(inst),
                            "now": now,
#                                        "solution": solution,
#                            "testResultList": res_arr if remove_CopyFileChecker else result,
                            "fileName": "proforma/response_student_visible_error.xml",
                            "gradername": "praktomat",
                            "graderversion": VERSION.version,
                            "namespace": grader.namespace})

        # response.write(get_http_error_page('Could not get submission files', str(inst), callstack))
        response.write(response_xml)
        response.status_code = 200 # file not found
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


class Proforma_Request:
    def __init__(self, request):
        self.request = request
        self.NAMESPACE = None
        self.NAMESPACES = {}
        self.proformatask = None
        self.root = None
        self.templatefile = None

    def yield_exception(self, inst, callstack):
        yield 'data: \n\n'
        yield 'data:     ' + str(inst) + '\n\n'
        yield 'data: \n\n'
        yield 'data: Praktomat: ' + VERSION.version + ' \n\n'
        yield 'data: \n\n'
        # lines = callstack.split('\n')
        lines = filter(str.strip, callstack.splitlines())
        for line in lines:
            yield "data: " + line + "\n\n"

    def run_test_yield_exc(self):
        try:
            yield from self.import_task(True)

            grader = grade.Grader(self.proformatask, self.NAMESPACE)
            logger.debug(self.NAMESPACES)
            yield "data: get submission files\n\n"
            submission_files, version_control = self.get_submission_files()  # returns a dictionary (filename -> content)

            # run tests
            yield from grader.grade(submission_files, version_control, True)
            # get result
            yield "data: get result\n\n"
            grade_result = grader.get_result(self.templatefile)

            # return result
            logger.debug("grading finished")
            logger.debug("--------------------")
            yield "data: RESPONSE START####\n\n"
            for line in grade_result.splitlines():
                # logger.debug(line)
                yield "data: " + line + "\n\n"
            yield "data: RESPONSE END####\n\n"

            # yield "data: " + grade_result + "\n\n"

#            response = HttpResponse()
#            response.write(grade_result)
#            response.status_code = 200
#            #        logger.debug("Number of solutions: " + str(Solution.objects.filter(task=proformatask).count()))
#            return response

            # send special characters and success result
            # yield "data: SUCCESS####\n\n"
        except task.TaskXmlException as inst:
            # import time
            yield "data: RESPONSE START####\n\n"
            yield "data: Task error\n\n"
            yield from self.yield_exception(inst, traceback.format_exc())
            yield "data: RESPONSE END####\n\n"
            # do not raise as the connection handling may get broken
            # raise
        except Exception as inst:
            import time
            yield "data: RESPONSE START####\n\n"
            yield "data: Error in grading process\n\n"
            yield from self.yield_exception(inst, traceback.format_exc())
            yield "data: RESPONSE END####\n\n"
            # do not raise as the connection handling may get broken
            # raise

    def import_task_yield_exc(self):
        try:
            yield from self.import_task(True)
            # send special characters and success result
            yield "data: SUCCESS####\n\n"
        except Exception as inst:
            import time
            yield "data: An exception occurred\n\n"
            yield 'data: ' + str(inst) + '\n\n'
            yield "data: Exception caught Stack Trace: " + "\n\n"
            callstack = traceback.format_exc()
            # lines = callstack.split('\n')
            lines = filter(str.strip, callstack.splitlines())
            for line in lines:
                yield "data: " + line + "\n\n"

            # send special characters and failure result
            yield "data: FAIL####\n\n"
            # do not raise as the connection handling may get broken
            # raise

    def import_task(self, upload = False):
        # get request XML from LMS (called 'submission.xml' in ProFormA)
        # yield 'data: read task meta data\n\n'
        xml = self.get_request_xml()
        logger.debug("type(xml): " + str(type(xml)))
        # logger.debug("got xml: " + xml)
        # debugging uploaded files
        # for field_name, file in request.FILES.items():
        #    filename = file.name
        #    logger.debug("grade_api_v2: request.Files: " + str(file) + "\tfilename: " + str(filename))
        # todo:
        # 1. check xml -> validate against xsd
        # 2. check uuid or download external xml
        # 3. files > file id all should be zipped
        # get xml version
        # xml_version = get_xml_version(submission_xml=xml)
        # do not validate for performance reasons
        # validate xsd
        # if xml_version:
        #    # logger.debug("xml: " + xml)
        #    is_valid = validate_xml(xml=xml, xml_version=xml_version)
        # else:
        #    logger.debug("no version - " + str(xml))
        #    is_valid = validate_xml(xml=xml)
        # logger.debug(xml)
        # note: we use lxml/etree here because it is very fast
        self.root = etree.fromstring(xml)
        # print ('NAMESPACE ' + root.xpath('namespace-uri(.)'))
        # print (root.nsmap[None])
        # NAMESPACES = {'dns': root.nsmap[None]}
        # print(root.nsmap)
        for key, value in self.root.nsmap.items():
            if key is None:
                if value == NAMESPACES_V2_0:
                    self.NAMESPACE = NAMESPACES_V2_0
                    self.templatefile = 'proforma/response_v2.0.xml'
                    self.NAMESPACES['dns'] = value
                elif value == NAMESPACES_V2_1:
                    self.NAMESPACE = NAMESPACES_V2_1
                    self.templatefile = 'proforma/response_v2.1.xml'
                    self.NAMESPACES['dns'] = value
                else:
                    raise Exception("do not support namespace " + value)
            else:
                if value.find('praktomat') >= 0:
                    self.NAMESPACES['praktomat'] = value
                else:
                    self.NAMESPACES[key] = value
        if self.NAMESPACE is None:
            raise Exception("no proforma namespace found")
        task_file = None
        task_filename = None
        task_element = self.root.find(".//dns:external-task", self.NAMESPACES)
        if task_element is not None:
            uri_element = task_element.find(".//dns:uri", self.NAMESPACES)
            if uri_element is not None:
                # new 2.1: external task is defined in sub element uri
                task_file, task_filename = self.get_external_task(uri_element.text)
            else:
                # old 2.1: external task is defined as text
                task_file, task_filename = self.get_external_task(task_element.text)
            # logger.debug('external-task in ' + task_path)
        else:
            task_element = self.root.find(".//dns:task", self.NAMESPACES)
            if task_element is not None:
                raise Exception("embedded task in submission.xml is not supported")
            else:
                task_element = self.root.find(".//dns:inline-task-zip", self.NAMESPACES)
                if task_element is not None:
                    raise Exception("inline-task-zip in submission.xml is not supported")
                else:
                    raise Exception("could not find task in submission.xml")
        # xml2dict is very slow
        # submission_dict = xml2dict(xml)
        if upload:
            logger.info("upload request for task " + task_filename)
        else:
            logger.info("grading request for task " + task_filename)

        logger.debug('import task')

        ptask = task.Proforma_Task()
        yield from ptask.import_task_internal(task_filename, task_file)
        self.proformatask = ptask.response_data
        # return NAMESPACE, NAMESPACES, proformatask, root, templatefile


    def get_external_task(self, task_uri):
        # logger.debug("task_uri: " + str(task_uri))
        ##
        # test file-field
        m = re.match(r"(http\-file\:)(?P<file_name>.+)", task_uri)
        file_name = None
        if m:
            file_name = m.group('file_name')
        else:
            raise Exception("unsupported external task URI: " + task_uri)

        logger.debug("file_name: " + str(file_name))
        for filename, file in list(self.request.FILES.items()):
            name = self.request.FILES[filename].name
            if name == file_name:
                task_filename = name
                task_file = file
                return task_file, task_filename

        raise Exception("could not find task with URI " + task_uri)


    def get_request_xml(self):
        """
        check the POST-Object
        1. could be just a submission.xml
        2. could be a submission.zip

        :rtype: submission.xml
        :param request:
        """
        # todo check encoding of the xml -> first line
        encoding = 'utf-8'
        if not self.request.POST:
            #if not request.FILES:
            #    raise KeyError("No submission attached")

            try:
                # submission.xml in request.Files
                logger.debug("FILES.keys(): " + str(list(self.request.FILES.keys())))
                if self.request.FILES['submission.xml'].name is not None:
                    xml = self.request.FILES['submission.xml'].read() # convert InMemoryUploadedFile to string
                    return xml
                elif self.request.FILES['submission.zip'].name:
                    # todo zip handling -> praktomat zip
                    raise Exception("zip handling is not implemented")
                else:
                    raise KeyError("No submission attached")
            except MultiValueDictKeyError:
                raise KeyError("No submission attached")
        else:
            logger.debug("got submission.xml as form data")
            xml = self.request.POST.get("submission.xml")

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



    def get_submission_file_from_request(self, searched_file_name):
        # remove beginning and trailing whitespaces
        searched_file_name = searched_file_name.strip()

        logger.debug("search submission file: '" + searched_file_name + "'")

        for filename, file in list(self.request.FILES.items()):
            name = self.request.FILES[filename].name
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



    def get_submission_files(self):
        NAMESPACES = self.NAMESPACES
        root = self.root

        ## TODO: read binary if possible and write binary without conversion

        # check for external submission
        submission_element = root.find(".//dns:external-submission", NAMESPACES)
        if submission_element is not None:
            uri_element = submission_element.find(".//dns:uri", NAMESPACES)
            if uri_element is not None:
                # new 2.1: external submission is defined in sub element uri
                submission_uri = uri_element.text
            else:
                # old 2.1: external task is defined as text
                submission_uri = submission_element.text

            # handle external submission
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
                    submission_files_dict.update(self.get_submission_file_from_request(searched_file_name))
                return submission_files_dict, None
            else:
                # expect submission from version control system
                # => figure out which system
                metadata_element = None
                if "praktomat" in NAMESPACES:
                    metadata_element = submission_element.find(".//praktomat:meta-data", NAMESPACES)

                if metadata_element is not None:
                    git_element = metadata_element.find(".//praktomat:git", NAMESPACES)
                    if git_element is not None:
                        logger.debug('GIT submission')
                        return self.get_submission_files_from_git(submission_uri)
                    svn_element = metadata_element.find(".//praktomat:svn", NAMESPACES)
                    if svn_element is not None:
                        logger.debug('SVN submission')
                        return self.get_submission_files_from_svn(submission_uri)
                    raise Exception('cannot determine source of external submission')
                else:
                    # SVN:
                    # export submission from URI
                    logger.debug('SVN submission')
                    return self.get_submission_files_from_svn(submission_uri)

        #embedded submission
        logger.debug('embedded submission')
        return self.get_submission_files_from_submission_xml()


    def get_submission_files_from_submission_xml(self):
        NAMESPACES = self.NAMESPACES
        root = self.root
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


    def get_submission_files_from_svn(self, submission_uri):
        from utilities.safeexec import execute_arglist
        from django.conf import settings

        folder = tempfile.mkdtemp()
        tmp_dir = os.path.join(folder, "submission")
        submission_uri = submission_uri.strip()
        cmd = ['svn', 'export', '--username', os.environ['SVNUSER'], '--password', os.environ['SVNPASS'], submission_uri,
               tmp_dir]
        # logger.debug(cmd)
        # fileseeklimit: do not limit here!
        [output, error, exitcode, timed_out, oom_ed] = \
            execute_arglist(cmd, folder, environment_variables={}, timeout=settings.TEST_TIMEOUT,
                            fileseeklimit=None,  # settings.TEST_MAXFILESIZE,
                            extradirs=[], unsafe=True)

        Proforma_Request.check_exitcode(error, exitcode, output, timed_out)
        # logger.debug('SVN-output: ' + output)
        # find revision
        m = re.search(r"(Exported revision )(?P<revision>.+)\.", output)
        revision = 'unknown revision'
        if m:
            if m.group('revision') is not None:
                revision = m.group('revision')
            logger.debug("SVN revision is: " + revision)

        versioncontrolinfo = Subversion(submission_uri, revision)

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



    def get_submission_files_from_git(self, submission_uri):
        """ get submission from gitlab/github or somewhere else """

        from utilities.safeexec import execute_arglist
        from django.conf import settings

        submission_uri = submission_uri.strip()

        user = os.environ['GITUSER']
        token = os.environ['GITPASS']
        if user is not None:
            user = user.strip()
            if len(user) > 0:
                if token is not None:
                    token = token.strip()
                else:
                    token = ""
                # we have credentials. Place them into uri.
                # https://username@github.com/username/repository.git
                # https://username:password@github.com/username/repository.git
                submission_with_creadentials_uri = submission_uri.replace('://', '://' + user + ':' + token + '@')

        # do not print, credentials are visible in commandline
        # print(submission_uri)

        folder = tempfile.mkdtemp()
        tmp_dir = os.path.join(folder, "submission")
        cmd = ['git', 'clone', submission_with_creadentials_uri, tmp_dir]
        # fileseeklimit: do not limit here!
        [output, error, exitcode, timed_out, oom_ed] = \
        execute_arglist(cmd, folder, environment_variables={}, timeout=settings.TEST_TIMEOUT,
                        fileseeklimit=None,  # settings.TEST_MAXFILESIZE,
                        extradirs=[], unsafe=True)
        Proforma_Request.check_exitcode(error, exitcode, output, timed_out)


        # find commit
        # cmd = ['git', 'log', '-1', '--pretty=format:%H']
        cmd = ['git', 'log', '-1', settings.GIT_LOG_FORMAT]

        [output, error, exitcode, timed_out, oom_ed] = \
        execute_arglist(cmd, tmp_dir, environment_variables={}, timeout=settings.TEST_TIMEOUT,
                        fileseeklimit=settings.TEST_MAXFILESIZE,
                        extradirs=[], unsafe=True)
        Proforma_Request.check_exitcode(error, exitcode, output, timed_out)
        logger.debug(output)

        versioncontrolinfo = Git(submission_uri, output.strip())

        # create filenames dictionary
        submission_files_dict = dict()
        import glob
        for file_name in glob.iglob(tmp_dir + '/**/*', recursive=True):
            if not os.path.isfile(file_name):  # ignore directories
                continue

            shortname = file_name[len(tmp_dir) + 1:]
            # logger.debug('add ' + str(shortname))
            submission_files_dict[shortname] = PhysicalFile(file_name)
        return submission_files_dict, versioncontrolinfo


    def check_exitcode(error, exitcode, output, timed_out):
        if exitcode != 0:
            message = ''
            if error != None:
                logger.debug('error: ' + str(error))
                message += error + ' '
            if output != None:
                logger.debug('output: ' + str(output))
                message += output
            raise ExternalSubmissionException(message.strip())

        if timed_out:
            raise ExternalSubmissionException('timeout')


