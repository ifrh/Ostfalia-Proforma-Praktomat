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
from operator import getitem

import xmlschema
#from django.views.decorators.csrf import csrf_exempt

from django.core.files import File
#from lxml import objectify


#from accounts.models import User
from checker.checker import PythonChecker, SetlXChecker
from checker.checker import CheckStyleChecker, JUnitChecker,  \
    CreateFileChecker
from checker.compiler import JavaBuilder, CBuilder
from os.path import dirname
from . import task
from tasks.models import Task
from django.conf import settings

import logging
from functools import reduce

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARENT_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
XSD_V_2_PATH = "xsd/proforma_v2.0.xsd"
SYSUSER = "sys_prod"

CACHE_TASKS = False
if not CACHE_TASKS:
    print('*********************************************\n')
    print('*** Attention! Tasks are not cached ! ***\n')
    print('*********************************************\n')




# wrapper for task object in Praktomat model
class Praktomat_Task_2_00:

    def __init__(self):
        self.__task = Task.objects.create(title="test",
                                          description="",
                                          submission_date=datetime.now(),
                                          publication_date=datetime.now())

    def __getTask(self):
        return self.__task
    object = property(__getTask)

    def __getitem_from_dict(self, dataDict, mapList):
        """Iterate nested dictionary"""
        return reduce(getitem, mapList, dataDict)


    def delete(self):
        self.__task.delete()
        self.__task = None

    def save(self):
        self.__task.save()

    def set_identifier_values(self, hash, task_uuid, task_title):
        self.__task.proformatask_hash = hash
        self.__task.proformatask_uuid = task_uuid
        self.__task.proformatask_title = task_title

    def read_basic_attributes(self, xml_dict):
        xml_description = xml_dict.get("description")
        if xml_description is None:
            self.__task.description = "No description"
        else:
            self.__task.description = xml_description

        xml_title = xml_dict.get("title")
        if xml_title is None:
            self.__task.title = "No title"
        else:
            self.__task.title = xml_title


    def read_submission_restriction(self, xml_dict):
        # todo add file restrictions

        path = ['submission-restrictions']
        max_size = None
        restriction = self.__getitem_from_dict(xml_dict, path)

        try:
            max_size = restriction.get("@max-size")
        except AttributeError:
            # no max size given => use default (1MB)
            max_size = 1000000

        # convert to KB
        self.__task.max_file_size = int(max_size) / 1024

#    def set_default_user(self, user_name):
#        try:
#            sys_user = User.objects.get(username=user_name)
#        except User.DoesNotExist:
#            sys_user = User.objects.create_user(username=user_name, email="creator@localhost")
#        #return sys_user


# wrapper for CreateFileChecker object
class Praktomat_File:
    def __init__(self, reffile, praktomatTask):
        self.__file_checker = CreateFileChecker.CreateFileChecker.objects.create(task=praktomatTask,
                                                                   order=1,
                                                                   path="")
        self.__file_checker.file = reffile  # check if the refid is there
        if dirname(reffile.name) is not None:
            self.__file_checker.path = dirname(reffile.name)
        self.__file_checker.always = True
        self.__file_checker.public = False
        self.__file_checker.required = False
        # save original filename in order to handle name clashes
        self.__file_checker.filename = os.path.basename(reffile.name)
        self.__file_checker.save()

        #logger.debug('Praktomat_File: file ' + str(self.__file_checker.file))
        #logger.debug('Praktomat_File: filename ' + str(self.__file_checker.filename))
        #logger.debug('Praktomat_File: path ' + str(self.__file_checker.path))

    def __getObject(self):
        return self.__file_checker
    object = property(__getObject)

    def __getFile(self):
        return self.__file_checker.file
    file = property(__getFile)

## ??? should we use this?
class Praktomat_Test_2_00:
    # todo: fill with content
    pass

class Task_2_00:
    format_namespace = "urn:proforma:v2.0"
    ns = {"p": format_namespace}

    # constructor
    def __init__(self, task_xml, xml_obj, hash, dict_zip_files=None):
        self.task_xml = task_xml
        self.xml_obj = xml_obj
        self.hash = hash
        self.dict_zip_files = dict_zip_files
        self.__praktomat_task = None
        self.xml_dict = None
        self.val_order = 1

    # (static) helper functions
    @staticmethod
    def __get_optional_xml_attribute_text(xmlTest, xpath, attrib, namespaces):
        if xmlTest.xpath(xpath, namespaces=namespaces) is None:
            return ""

        try:
            return xmlTest.xpath(xpath, namespaces=namespaces)[0].attrib.get(attrib)
        except:
            return ""

    def __get_optional_xml_element_text(self, xmlTest, xpath):
        try:
            if xmlTest.xpath(xpath, namespaces=self.ns) is not None:
                return xmlTest.xpath(xpath, namespaces=self.ns)[0].text
        except:
            return ""

    def __get_required_xml_element_text(self, xmlTest, xpath, namespaces, msg):
        if xmlTest.xpath(xpath, namespaces=namespaces) is None:
            raise task.TaskXmlException(msg + ' is missing')

        text = xmlTest.xpath(xpath, namespaces=namespaces)[0].text

        if text is None or len(text) == 0:
            raise task.TaskXmlException(msg + ' must not be empty')
        return text

    # read all files from task and put them into a dictionary
    def __create_praktomat_files(self, xml_obj, external_file_dict=None, ):
        namespace = self.ns

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
                    if external_file_dict is None:
                        raise Exception('no files in zip found')
                    logger.debug('attached task file: ' + k.attrib.get("id") + ' => ' + filename)
                    orphain_files[k.attrib.get("id")] = external_file_dict[filename]
                else:
                    raise Exception('unsupported file type in task.xml (embedded-bin-file or attached-txt-file)')

        # List with all files that are referenced by tests
        list_of_test_files = xml_obj.xpath("/p:task/p:tests/p:test/p:test-configuration/"
                                           "p:filerefs/p:fileref/@refid", namespaces=namespace)
        # Remove duplicates from list (for files that are referenced by more than one test)!!
        list_of_test_files = list(dict.fromkeys(list_of_test_files))
        # Create dictionary with Praktomat Checker files
        self.checker_files = dict()
        for test_ref_id in list_of_test_files:
            if not test_ref_id in orphain_files:
                raise task.TaskXmlException('file ' + str(test_ref_id) + ' is not in task files or used_by_grader = false')
            file = orphain_files.pop(test_ref_id, "")
            self.checker_files[test_ref_id] = Praktomat_File(file, self.__praktomat_task.object)

        if len(orphain_files)> 0:
            logger.error('orphain files found')


    def __set_test_base_parameters(self, inst, xmlTest):
        if xmlTest.xpath("p:title", namespaces=self.ns) is not None:
            inst.name = xmlTest.xpath("p:title", namespaces=self.ns)[0].text
        #if (xmlTest.xpath("p:title", namespaces=ns) and xmlTest.xpath("p:title", namespaces=ns)[0].text):
        #    inst.name = xmlTest.xpath("p:title", namespaces=ns)[0].text
        inst.test_description = self.__get_optional_xml_element_text(xmlTest, "p:description")
        inst.proforma_id = xmlTest.attrib.get("id")  # required attribute!!
        inst.always = True
        inst.public = True
        inst.required = False

    # add files belonging to a subtest
    def __add_files_to_test(self, xml_test, firstHandler = None, inst = None):
        for fileref in xml_test.xpath("p:test-configuration/p:filerefs/p:fileref", namespaces=self.ns):
            refid = fileref.attrib.get("refid")
            if not refid in self.checker_files:
                raise task.TaskXmlException('cannot find file with id = ' + refid)
            praktomat_file = self.checker_files[refid]
            logger.debug('handle test file ' + str(refid))
            if firstHandler is not None:
                logger.debug('handle first test file')
                firstHandler(inst, praktomat_file.file)
                firstHandler = None
            else:
                logger.debug('create normal test file')
                self.val_order += 1  # to push the junit-checker behind create-file checkers
                logger.debug('__add_files_to_test: increment vald_order, new value= ' + str(self.val_order))
                inst.files.add(praktomat_file.object)


    def __create_java_compilertest(self, xmlTest):
        inst = JavaBuilder.JavaBuilder.objects.create(task=self.__praktomat_task.object,
                                                      order=self.val_order,
                                                      _flags="",
                                                      _output_flags="",
                                                      _file_pattern=r"^.*\.[jJ][aA][vV][aA]$",
                                                      _main_required=False
                                                      )

        self.__set_test_base_parameters(inst, xmlTest)
        inst.save()


    def __create_java_unit_test(self, xmlTest):
        checker_ns = self.ns.copy()
        checker_ns['unit_new'] = 'urn:proforma:tests:unittest:v1.1'
        checker_ns['unit'] = 'urn:proforma:tests:unittest:v1'

        inst = JUnitChecker.JUnitChecker.objects.create(task=self.__praktomat_task.object, order=self.val_order)
        self.__set_test_base_parameters(inst, xmlTest)
        #if xmlTest.xpath("p:title", namespaces=ns) is not None:
        #        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
        #inst.test_description = geget_required_xml_element_textt_optional_xml_element_text(xmlTest, "p:description", ns)

        inst.class_name = self.__get_required_xml_element_text(xmlTest,
            "p:test-configuration/unit_new:unittest/unit_new:entry-point", checker_ns, 'JUnit entrypoint')

        junit_version = ''
        if xmlTest.xpath("p:test-configuration/unit:unittest[@framework='JUnit']", namespaces=checker_ns):
            junit_version = Task_2_00.__get_optional_xml_attribute_text(xmlTest,
                "p:test-configuration/unit:unittest[@framework='JUnit']", "version", checker_ns)
        elif xmlTest.xpath("p:test-configuration/unit_new:unittest[@framework='JUnit']", namespaces=checker_ns):
            junit_version = Task_2_00.__get_optional_xml_attribute_text(xmlTest,
                "p:test-configuration/unit_new:unittest[@framework='JUnit']", "version", checker_ns)

        if len(junit_version) == 0:
            raise Exception('Task XML error: Junit Version is missing')

        version = re.split('\.', junit_version)

        inst.junit_version = "junit" + junit_version
        logger.debug("JUNIT-version is " + inst.junit_version)

        try:
            # check if version is supported
            settings.JAVA_LIBS[inst.junit_version]
        except Exception as e:
            inst.delete()
            # todo create: something like TaskException class
            raise Exception("Junit-Version is not supported: " + str(junit_version))

        self.__add_files_to_test(xmlTest, None, inst)

        inst.order = self.val_order
        inst.save()

    def __create_java_checkstyle_test(self, xmlTest):
        checker_ns = self.ns.copy()
        checker_ns['check'] = 'urn:proforma:tests:java-checkstyle:v1.1'

        inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=self.__praktomat_task.object, order=self.val_order)
        self.__set_test_base_parameters(inst, xmlTest)
        if xmlTest.xpath("p:test-configuration/check:java-checkstyle",
                         namespaces=checker_ns)[0].attrib.get("version"):
            checkstyle_ver = xmlTest.xpath("p:test-configuration/check:java-checkstyle", namespaces=checker_ns)[0].\
                attrib.get("version")

            # check if checkstlye version is configured
            inst.check_version = 'check-' + checkstyle_ver.strip()
            logger.debug('checkstyle version: ' + inst.check_version)
            try:
                # check if version is supported
                bin = settings.CHECKSTYLE_VER[inst.check_version]
            except Exception as e:
                inst.delete()
                # todo create: something like TaskException class
                raise Exception("Checkstyle-Version is not supported: " + str(checkstyle_ver))


        if xmlTest.xpath("p:test-configuration/check:java-checkstyle/"
                         "check:max-checkstyle-warnings", namespaces=checker_ns):
            inst.allowedWarnings = xmlTest.xpath("p:test-configuration/"
                                                 "check:java-checkstyle/"
                                                 "check:max-checkstyle-warnings", namespaces=checker_ns)[0]

        def set_mainfile(inst, value):
            inst.configuration = value
        self.__add_files_to_test(xmlTest, set_mainfile, inst)
        inst.order = self.val_order
        inst.save()


    def __create_setlx_test(self, xmlTest):
        inst = SetlXChecker.SetlXChecker.objects.create(task=self.__praktomat_task.object, order=self.val_order)
        self.__set_test_base_parameters(inst, xmlTest)
        def set_mainfile(inst, value):
            inst.testFile = value
        self.__add_files_to_test(xmlTest, firstHandler=set_mainfile, inst=inst)
        inst.save()


    def __create_python_test(self, xmlTest):
        inst = PythonChecker.PythonChecker.objects.create(task=self.__praktomat_task.object, order=self.val_order)
        self.__set_test_base_parameters(inst, xmlTest)
        def set_mainfile(inst, value):
            inst.doctest = value
        self.__add_files_to_test(xmlTest, firstHandler=set_mainfile, inst=inst)
        inst.save()


    # todo???
    # proglang -> e.g Java 1.6 / Python 2.7
    # files : used-by-grader="true"

    # MAIN FUNCTION OF CLASS
    # tests
    #   compiler
    #   JUNIT
    #   Checkstyle
    def import_task(self):

        task_in_xml = self.xml_obj.xpath("/p:task", namespaces=self.ns)
        task_uuid = task_in_xml[0].attrib.get("uuid")
        logger.debug('uuid is ' + task_uuid)
        task_title = self.xml_obj.xpath("/p:task/p:title", namespaces=self.ns)[0]
        logger.debug('title is "' + task_title + '"')

        # check if task is already in database
        if CACHE_TASKS:
            old_task = task.get_task(self.hash, task_uuid, task_title)
            if old_task != None:
                return old_task

        # no need to actually validate xml against xsd
        # (it is only time consuming)
        schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
        # todo: remove because it is very expensive (bom, about 350ms)
        # logger.debug('task_xml = ' + str(task_xml))
        t = tempfile.NamedTemporaryFile(delete=True)
        t.write(self.task_xml)
        t.flush()
        t.seek(0)

        self.xml_dict = schema.to_dict(t)

        # xml_dict = validate_xml(xml=task_xml)

        # xml_obj = objectify.fromstring(xml_object) # task_xml)

        self.__praktomat_task = Praktomat_Task_2_00()
        try:
            self.__praktomat_task.read_basic_attributes(self.xml_dict)
            self.__praktomat_task.read_submission_restriction(self.xml_dict)
            # self.set_default_user(user_name=SYSUSER)

            # read files
            self.__create_praktomat_files(xml_obj=self.xml_obj, external_file_dict=self.dict_zip_files)
            # create test objects
            for xmlTest in self.xml_obj.tests.iterchildren():
                testtype = xmlTest.xpath("p:test-type", namespaces=self.ns)[0].text
                if testtype == "java-compilation":  # todo check compilation_xsd
                    logger.debug('** create_java_compilertest')
                    self.__create_java_compilertest(xmlTest)
                elif testtype == "unittest":
                    logger.debug('** create_java_unit_test')
                    self.__create_java_unit_test(xmlTest)
                elif testtype == "java-checkstyle":
                    self.__create_java_checkstyle_test(xmlTest)
                elif testtype == "setlx": # and xmlTest.xpath("p:test-configuration/jartest:jartest[@framework='setlX']", namespaces=ns):
                    self.__create_setlx_test(xmlTest)
                elif testtype == "python-doctest":
                    logger.debug('** create_python_test')
                    self.__create_python_test(xmlTest)
                self.val_order += 1
                logger.debug('increment vald_order, new value= ' + str(self.val_order))

        except Exception:
            self.__praktomat_task.delete()
            self.__praktomat_task = None
            ### TODO delete files (memory leak)????
            raise

        # finally set identifier attributes (do not set in previous steps
        # in order to avoid a broken task to be stored
        self.__praktomat_task.set_identifier_values(self.hash, task_uuid, task_title)
        self.__praktomat_task.save()
        return self.__praktomat_task.object

    # def validate_xml(xml, xml_version=None):
    #     if xml_version is None:
    #         schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
    #         #try:
    #         #    schema.validate(xml)
    #         #except Exception as e:
    #         #    logger.error("Schema is not valid: " + str(e))
    #         #    raise Exception("Schema is not valid: " + str(e))
    #     return schema.to_dict(xml)
