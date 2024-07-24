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
# functions for importing ProFormA tasks into Praktomat database

import re
import os
import tempfile
from datetime import datetime

import xmlschema

from django.core.files import File

from checker.checker import PythonChecker, PythonUnittestChecker, SetlXChecker
from checker.checker import CheckStyleChecker, JUnitChecker,  \
    CreateFileChecker, MakeChecker, GoogleTestChecker
from checker.compiler import JavaBuilder
from os.path import dirname
from . import task
from tasks.models import Task
from django.conf import settings
from . import sandbox

import logging

logger = logging.getLogger(__name__)

# BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARENT_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
XSD_V_2_PATH = "proforma/xsd/proforma_v2.0.xsd"
XSD_V_2_01_PATH = "proforma/xsd/proforma_2.0.1_rc.xsd"
XSD_V_2_1_PATH = "proforma/xsd/proforma_2.1.xsd"
# SYSUSER = "sys_prod"

CACHE_TASKS = True
if not CACHE_TASKS:
    print('*********************************************\n')
    print('*** Attention! Tasks are not cached ! ***\n')
    print('*********************************************\n')



# helper functions
def get_optional_xml_element_text(xmlTest, xpath, namespaces):
    try:
        if xmlTest.xpath(xpath, namespaces=namespaces) is not None:
            return xmlTest.xpath(xpath, namespaces=namespaces)[0].text
    except:
        return ""


def get_required_xml_element_text(xmlTest, xpath, namespaces, msg):
    if xmlTest.xpath(xpath, namespaces=namespaces) is None:
        raise task.TaskXmlException(msg + ' is missing')

    text = xmlTest.xpath(xpath, namespaces=namespaces)[0].text

    if text is None or len(text) == 0:
        raise task.TaskXmlException(msg + ' must not be empty')
    return text

def _get_required_xml_element(xmlTest, xpath, namespaces, message):
    element = xmlTest.xpath(xpath, namespaces=namespaces)
    if len(element) == 0:
        raise task.TaskXmlException('missing ' + message)
    if len(element) > 1:
        raise task.TaskXmlException('more than one ' + message + ' found')
    return element[0]

def _get_optional_xml_element(xmlTest, xpath, namespaces, message):
    element = xmlTest.xpath(xpath, namespaces=namespaces)
    if len(element) == 0:
        return None
    if len(element) > 1:
        raise task.TaskXmlException('more than one ' + message + ' found')
    return element[0]


# wrapper for task object in Praktomat model
class Praktomat_Task_2_00:

    def __init__(self):
        self._task = Task.objects.create(title="test",
                                         description="",
                                         # submission_date=datetime.now(),
                                         publication_date=datetime.now())

    def _getTask(self):
        return self._task
    object = property(_getTask)

    def delete(self):
        self._task.delete()
        self._task = None

    def save(self):
        self._task.save()

    def set_identifier_values(self, hash, task_uuid, task_title):
        self._task.proformatask_hash = hash
        self._task.proformatask_uuid = task_uuid
        self._task.proformatask_title = task_title

    def read(self, xml_dict):
        self._read_basic_attributes(xml_dict)
        self._read_submission_restriction(xml_dict)

    def _read_basic_attributes(self, xml_dict):
        xml_description = xml_dict.get("description")
        if xml_description is None:
            self._task.description = "No description"
        else:
            self._task.description = xml_description

        xml_title = xml_dict.get("title")
        if xml_title is None:
            self._task.title = "No title"
        else:
            self._task.title = xml_title


    def _read_submission_restriction(self, xml_dict):
        # todo add file restrictions

        max_size = None
        restriction = xml_dict.get('p:submission-restrictions')

        try:
            max_size = restriction.get("@max-size")
        except AttributeError:
            logger.debug('could not find max-size, set to default')
            # no max size given => use default (1MB)
            max_size = 1000000

        # convert to KB
        self._task.max_file_size = int(max_size) / 1024

#    def set_default_user(self, user_name):
#        try:
#            sys_user = User.objects.get(username=user_name)
#        except User.DoesNotExist:
#            sys_user = User.objects.create_user(username=user_name, email="creator@localhost")
#        #return sys_user


# wrapper for CreateFileChecker object (= file object in Praktomat model)
class Praktomat_File:
    def __init__(self, file, praktomatTask):
        self._file_checker = CreateFileChecker.CreateFileChecker.objects.create(task=praktomatTask,
                                                                                order=1,
                                                                                path="")
        self._file_checker.file = file  # check if the refid is there
        if dirname(file.name) is not None:
            self._file_checker.path = dirname(file.name)
        self._file_checker.always = True
        self._file_checker.public = False
        self._file_checker.required = False
        # save original filename in order to handle name clashes
        self._file_checker.filename = os.path.basename(file.name)
        self._file_checker.save()

    def _getObject(self):
        return self._file_checker
    object = property(_getObject)

    def _getFile(self):
        return self._file_checker.file
    file = property(_getFile)


# wrapper for checker object (= test object in Praktomat model)
class Praktomat_Test_2_0:
    def __init__(self, inst, namespaces):
        self._checker = inst
        self._ns = namespaces

    def set_test_base_parameters(self, xmlTest):
        if xmlTest.xpath("p:title", namespaces=self._ns) is not None:
            self._checker.name = xmlTest.xpath("p:title", namespaces=self._ns)[0].text
            self._checker.test_description = get_optional_xml_element_text(xmlTest, "p:description", self._ns)
        self._checker.proforma_id = xmlTest.attrib.get("id")  # required attribute!!
        self._checker.always = True
        self._checker.public = True
        self._checker.required = True

    # add files belonging to a subtest
    def add_files_to_test(self, xml_test, praktomat_files, val_order, firstHandler = None):
        for fileref in xml_test.xpath("p:test-configuration/p:filerefs/p:fileref", namespaces=self._ns):
            refid = fileref.attrib.get("refid")
            if not refid in praktomat_files:
                raise task.TaskXmlException('cannot find file with id = ' + refid)
            praktomat_file = praktomat_files[refid]
            logger.debug('handle test file ' + str(refid))
            if firstHandler is not None:
                logger.debug('handle first test file')
                firstHandler(self._checker, praktomat_file.file)
                firstHandler = None
            else:
                logger.debug('create normal test file')
                val_order += 1  # to push the junit-checker behind create-file checkers
                logger.debug('add_files_to_test: increment vald_order, new value= ' + str(val_order))
                self._checker.files.add(praktomat_file.object)

        self._checker.order = val_order
        return val_order

    def save(self):
        self._checker.save()


class Task_2_00:
    # constructor
    def __init__(self, task_xml, xml_obj, hash, dict_zip_files, format_namespace):
        self._task_xml = task_xml
        self._xml_obj = xml_obj
        self._hash = hash
        self._dict_zip_files = dict_zip_files
        self._praktomat_task = None
        self._val_order = 1
        self._praktomat_files = None
        self._format_namespace = format_namespace
        self._ns = {"p": self._format_namespace}
        # result from import_task is stored as member
        # variable in order to send progress information
        # to the client (use generator approach)
        self._imported_task = None

    @property
    def imported_task(self):
        return self._imported_task

    # read all files from task and put them into a dictionary
    def _create_praktomat_files(self, xml_obj, external_file_dict=None, ):
        namespace = self._ns

        orphain_files = dict()

        # read all files with 'used-by-grader' = true
        for k in xml_obj.xpath("/p:task/p:files/p:file", namespaces=namespace):
            # todo add: embedded-bin-file
            # todo??: attached-txt-file can lead to problems with encoding (avoid attached-txt-file!)
            used_by_grader = k.attrib.get('used-by-grader')
            if used_by_grader == "true":
                if k.xpath("p:embedded-txt-file", namespaces=namespace):
                    t = tempfile.NamedTemporaryFile(delete=True)
                    t.write(k['embedded-txt-file'].text.encode("utf-8"))
                    t.flush()
                    my_temp = File(t)
                    my_temp.name = k['embedded-txt-file'].attrib.get("filename")
                    logger.debug('embedded task file: ' + k.attrib.get("id") + ' => ' + my_temp.name)
                    orphain_files[k.attrib.get("id")] = my_temp
                elif k.xpath("p:attached-bin-file", namespaces=namespace):
                    filename = k['attached-bin-file'].text
                    logger.debug('attached task file: ' + k.attrib.get("id") + ' => ' + filename)
                    orphain_files[k.attrib.get("id")] = external_file_dict[filename]
                elif k.xpath("p:attached-txt-file", namespaces=namespace):
                    filename = k['attached-txt-file'].text
                    logger.debug('attached task file: ' + k.attrib.get("id") + ' => ' + filename)
                    orphain_files[k.attrib.get("id")] = external_file_dict[filename]
                elif k.xpath("p:embedded-bin-file", namespaces=namespace):
                    import base64
                    t = tempfile.NamedTemporaryFile(delete=True)
                    t.write(base64.b64decode(k['embedded-bin-file'].text))
                    t.flush()
                    my_temp = File(t)
                    my_temp.name = k['embedded-bin-file'].attrib.get("filename")
                    logger.debug('embedded task file: ' + k.attrib.get("id") + ' => ' + my_temp.name)
                    orphain_files[k.attrib.get("id")] = my_temp
                else:
                    raise task.TaskXmlException('no file element found')

        # List with all files that are referenced by tests
        list_of_test_files = xml_obj.xpath("/p:task/p:tests/p:test/p:test-configuration/"
                                           "p:filerefs/p:fileref/@refid", namespaces=namespace)
        # Remove duplicates from list (for files that are referenced by more than one test)!!
        list_of_test_files = list(dict.fromkeys(list_of_test_files))
        # Create dictionary with Praktomat Checker files
        self._praktomat_files = dict()
        for test_ref_id in list_of_test_files:
            if not test_ref_id in orphain_files:
                raise task.TaskXmlException('file ' + str(test_ref_id) + ' is not in task files or used_by_grader = false')
            file = orphain_files.pop(test_ref_id, "")
            self._praktomat_files[test_ref_id] = Praktomat_File(file, self._praktomat_task.object)

        if len(orphain_files)> 0:
            logger.error('orphain files found')


    def _create_java_compilertest(self, xmlTest):
        inst = JavaBuilder.JavaBuilder.objects.create(task=self._praktomat_task.object,
                                                      order=self._val_order,
                                                      _flags="",
                                                      _output_flags="",
                                                      _file_pattern=r"^.*\.[jJ][aA][vV][aA]$",
                                                      _main_required=False
                                                      )
        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        x.save()




    def _create_java_unit_test(self, xmlTest):
        # create list with valid namespaces for unit test
        checker_ns = self._ns.copy() # base: default namespace
        checker_ns['unit_1.1'] = 'urn:proforma:tests:unittest:v1.1' # append unittest 1.1 namespace
        # checker_ns['unit'] = 'urn:proforma:tests:unittest:v1'

        inst = JUnitChecker.JUnitChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)

        # get unittest element
        unittest = _get_required_xml_element(xmlTest, "p:test-configuration/unit_1.1:unittest",
                                             checker_ns, 'unittest element for testconfiguration = \'unittest\'')

        # get junit version
        junit_version = ''
        framework = unittest.attrib.get("framework")
        if framework == None:
            raise task.TaskXmlException('unittest framework missing (is it JUnit?)')
        framework = framework.lower()
        if framework != 'junit':
            raise task.TaskXmlException('unknown test framework (only junit is supported)')
        junit_version = unittest.attrib.get("version")

        if junit_version == None or len(junit_version) == 0:
            raise task.TaskXmlException('Junit Version is missing')

        version = re.split('\.', junit_version)

        inst.junit_version = "junit" + junit_version
        logger.debug("JUNIT-version is " + inst.junit_version)

        try:
            # check if version is supported
            settings.JAVA_LIBS[inst.junit_version]
        except Exception as e:
            # try and guess version :-(
            logger.error("JUNIT-version is " + inst.junit_version)
            logger.error("Junit-Version not found: \'" + str(junit_version) + "\', try other")
            try:
                junit_version = re.split(' ', junit_version)
                inst.junit_version = "junit" + junit_version[0]
                settings.JAVA_LIBS[inst.junit_version]
            except Exception as e:
                inst.delete()
                # todo create: something like TaskException class
                raise task.TaskXmlException("Junit-Version is not supported: \'" + str(junit_version) + "\'")
            logger.error("JUNIT-version is now: \'" + junit_version[0] + "\'")

        # get entrypoint
        inst.class_name = get_required_xml_element_text(unittest, "unit_1.1:entry-point", checker_ns, 'JUnit entrypoint').strip()

        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, None)
        x.save()

    def _create_c_unit_test(self, xmlTest):
        # create list with valid namespaces for unit test
        checker_ns = self._ns.copy() # base: default namespace
        checker_ns['unit_1.1'] = 'urn:proforma:tests:unittest:v1.1'

        inst = MakeChecker.MakeChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)

        # get unittest element
        unittest = _get_required_xml_element(xmlTest, "p:test-configuration/unit_1.1:unittest",
                                             checker_ns, 'unittest element for testconfiguration = \'unittest\'')

        # get entrypoint
        inst.class_name = get_required_xml_element_text(unittest, "unit_1.1:entry-point", checker_ns, 'CUnit entrypoint').strip()

        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, None)
        x.save()

    def _create_cpp_unit_test(self, xmlTest):
        # create list with valid namespaces for unit test
        checker_ns = self._ns.copy() # base: default namespace
        checker_ns['unit_1.1'] = 'urn:proforma:tests:unittest:v1.1'

        inst = GoogleTestChecker.GoogleTestChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)

        # get unittest element
        unittest = _get_required_xml_element(xmlTest, "p:test-configuration/unit_1.1:unittest",
                                             checker_ns, 'unittest element for testconfiguration = \'unittest\'')

        # get entrypoint, i.e. run command
        inst.exec_command = get_required_xml_element_text(unittest, "unit_1.1:entry-point", checker_ns, 'Googletest entrypoint').strip()

        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, None)
        x.save()

    def _create_python_unit_test(self, xmlTest):
        # create list with valid namespaces for unit test
        checker_ns = self._ns.copy() # base: default namespace
        checker_ns['unit_1.1'] = 'urn:proforma:tests:unittest:v1.1'

        inst = PythonUnittestChecker.PythonUnittestChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)

        # get unittest element
        # unittest = _get_required_xml_element(xmlTest, "p:test-configuration/unit_1.1:unittest",
        #                                     checker_ns, 'unittest element for testconfiguration = \'unittest\'')

        # get entrypoint, i.e. run command
        # inst.exec_command = get_required_xml_element_text(unittest, "unit_1.1:entry-point", checker_ns, 'Googletest entrypoint').strip()

        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, None)

        requirements_txt = inst.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) != 0:
            requirements_txt = requirements_txt.first()
            requirements_path = os.path.join(settings.UPLOAD_ROOT,
                                         task.get_storage_path(requirements_txt, requirements_txt.filename))
        else:
            requirements_path = None

        image = sandbox.PythonImage(inst, requirements_path)
#        image.check_preconditions()
        x.save()
        # Check preconditions for image
#        requirements_txt = inst.files.filter(filename='requirements.txt', path='')
#        if len(requirements_txt) > 1:
#            raise Exception('more than one requirements.txt found')
        yield 'data: create sandbox image for python unit test\n\n'
        yield from image.create_image_yield()

    def _create_java_checkstyle_test(self, xmlTest):
        checker_ns = self._ns.copy()
        checker_ns['check'] = 'urn:proforma:tests:java-checkstyle:v1.1'

        # checkstyle = xmlTest.xpath("p:test-configuration/check:java-checkstyle", namespaces=checker_ns)
        checkstyle = _get_optional_xml_element(xmlTest, "p:test-configuration/check:java-checkstyle",
                                             checker_ns, 'checkstyle element for testconfiguration = \'checkstyle\'')


        inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)
        checkstyle_ver = None
        if checkstyle != None:
            checkstyle_ver = checkstyle.attrib.get("version")

        if checkstyle_ver == None:
            logger.debug('keys: ' + str(list(settings.CHECKSTYLE_VER.keys())))
            inst.check_version = list(settings.CHECKSTYLE_VER.keys())[-1]
            logger.error("No Checkstyle version defined, pick : \'" + inst.check_version + "\'")
            checkstyle_ver = inst.check_version
        else:
            inst.check_version = 'check-' + checkstyle_ver.strip()

        # check if checkstlye version is configured
        logger.debug('checkstyle version: ' + inst.check_version)
        try:
            # check if version is supported
            bin = settings.CHECKSTYLE_VER[inst.check_version]
        except Exception as e:
            inst.delete()
            # todo create: something like TaskException class
            raise task.TaskXmlException("Checkstyle-Version is not supported: " + str(checkstyle_ver))


        if xmlTest.xpath("p:test-configuration/check:java-checkstyle/"
                         "check:max-checkstyle-warnings", namespaces=checker_ns):
            inst.allowedWarnings = xmlTest.xpath("p:test-configuration/"
                                                 "check:java-checkstyle/"
                                                 "check:max-checkstyle-warnings", namespaces=checker_ns)[0]

        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        def set_mainfile(inst, value):
            inst.configuration = value
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, set_mainfile)
        # inst.order = self._val_order
        x.save()


    def _create_setlx_test(self, xmlTest):
        inst = SetlXChecker.SetlXChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)
        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        def set_mainfile(inst, value):
            inst.testFile = value
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, firstHandler=set_mainfile)
        x.save()


    def _create_python_test(self, xmlTest):
        inst = PythonChecker.PythonChecker.objects.create(task=self._praktomat_task.object, order=self._val_order)
        x = Praktomat_Test_2_0(inst, self._ns)
        x.set_test_base_parameters(xmlTest)
        def set_mainfile(inst, value):
            inst.doctest = value
        self._val_order = x.add_files_to_test(xmlTest, self._praktomat_files, self._val_order, firstHandler=set_mainfile)
        x.save()

    def _get_xsd_path(self):
        if self._format_namespace == 'urn:proforma:v2.0':
            return XSD_V_2_PATH
        if self._format_namespace == 'urn:proforma:v2.0.1':
            return XSD_V_2_01_PATH
        if self._format_namespace == 'urn:proforma:v2.1':
            return XSD_V_2_1_PATH
        raise task.TaskXmlException('ProForma XSD not found for namespace ' + self._format_namespace)

    def import_task(self):
        task_in_xml = self._xml_obj.xpath("/p:task", namespaces=self._ns)
        task_uuid = task_in_xml[0].attrib.get("uuid")
        logger.debug('uuid is ' + task_uuid)
        task_title = self._xml_obj.xpath("/p:task/p:title", namespaces=self._ns)[0]
        logger.debug('title is "' + task_title + '"')
        yield 'data: import task\n\n'
#        yield 'data: Import task "' + task_title + '"\n\n'
        task_proglang = self._xml_obj.xpath("/p:task/p:proglang", namespaces=self._ns)[0]
        logger.debug('proglang is "' + task_proglang + '"')


        # check if task is already in database
        if CACHE_TASKS:
            old_task = task.get_task(self._hash, task_uuid, task_title)
            if old_task is not None:
                logger.debug('task already exists, no import')
                yield 'data: task already exists, no import\n\n'
                self._imported_task = old_task
                return
                # return old_task

        yield 'data: extract task\n\n'
        # no need to actually validate xml against xsd
        # (it is only time consuming)
        schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, self._get_xsd_path()))
        # todo: remove because it is very expensive (bom, about 350ms)
        # logger.debug('task_xml = ' + str(task_xml))
        t = tempfile.NamedTemporaryFile(delete=True)
        t.write(self._task_xml)
        t.flush()
        t.seek(0)

        xml_dict = schema.to_dict(t)
        if xml_dict == None:
            raise Exception('cannot create dictionary from task')

        # xml_dict = validate_xml(xml=task_xml)

        # xml_obj = objectify.fromstring(xml_object) # task_xml)

        self._praktomat_task = Praktomat_Task_2_00()
        try:
            self._praktomat_task.read(xml_dict)
            # self.set_default_user(user_name=SYSUSER)

            # read files
            yield 'data: create files\n\n'
            self._create_praktomat_files(xml_obj=self._xml_obj, external_file_dict=self._dict_zip_files)
            # create test objects
            yield 'data: create tests\n\n'
            for xmlTest in self._xml_obj.tests.iterchildren():
                testtype = xmlTest.xpath("p:test-type", namespaces=self._ns)[0].text
                if testtype == "java-compilation":  # todo check compilation_xsd
                    logger.debug('** create_java_compilertest')
                    self._create_java_compilertest(xmlTest)
                elif testtype == "unittest":
                    if task_proglang == 'java':
                        logger.debug('** create_java_unit_test')
                        self._create_java_unit_test(xmlTest)
                    elif task_proglang == 'c':
                        logger.debug('** create_c_unit_test')
                        self._create_c_unit_test(xmlTest)
                    elif task_proglang == 'cpp':
                        logger.debug('** create_cpp_unit_test')
                        self._create_cpp_unit_test(xmlTest)
                    elif task_proglang == 'python':
                        logger.debug('** create_python_unit_test')
                        yield from self._create_python_unit_test(xmlTest)
                    else:
                        raise task.TaskXmlException('invalid proglang, supported is java and c')
                elif testtype == "java-checkstyle":
                    self._create_java_checkstyle_test(xmlTest)
                elif testtype == "setlx": # and xmlTest.xpath("p:test-configuration/jartest:jartest[@framework='setlX']", namespaces=ns):
                    self._create_setlx_test(xmlTest)
                elif testtype == "python-doctest":
                    logger.debug('** create_python_test')
                    self._create_python_test(xmlTest)
                self._val_order += 1
                logger.debug('increment val_order, new value= ' + str(self._val_order))

        except Exception:
            # delete objects
            self._praktomat_task.delete()
            self._praktomat_task = None
            for file in self._praktomat_files.values():
                file.object.delete()
            raise

        # finally set identifier attributes (do not set in previous steps
        # in order to avoid a broken task to be stored
        self._praktomat_task.set_identifier_values(self._hash, task_uuid, task_title)
        yield 'data: save\n\n'
        self._praktomat_task.save()
        # return self._praktomat_task.object

        self._imported_task = self._praktomat_task.object
        yield 'data: task is successfully imported\n\n'

    # def validate_xml(xml, xml_version=None):
    #     if xml_version is None:
    #         schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
    #         #try:
    #         #    schema.validate(xml)
    #         #except Exception as e:
    #         #    logger.error("Schema is not valid: " + str(e))
    #         #    raise Exception("Schema is not valid: " + str(e))
    #     return schema.to_dict(xml)
