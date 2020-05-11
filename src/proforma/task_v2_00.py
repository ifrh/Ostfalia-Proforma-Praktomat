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
import json
from operator import getitem

import xmlschema
from django.views.decorators.csrf import csrf_exempt

from django.core.files import File
from django.http import HttpResponse
from lxml import objectify


from accounts.models import User
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


class TaskXmlException(Exception):
    pass


# wrapper for task object in Praktomat model
class Praktomat_Task_2_00:

    def __init__(self):
        self._task = Task.objects.create(title="test",
                                       description="",
                                       submission_date=datetime.now(),
                                       publication_date=datetime.now())

    def __getTask(self):
        return self._task

    def __getitem_from_dict(self, dataDict, mapList):
        """Iterate nested dictionary"""
        return reduce(getitem, mapList, dataDict)

    praktomatTask = property(__getTask)

    def delete(self):
        self._task.delete()
        self._task = None

    def save(self):
        self._task.save()

    def set_identifier_values(self, hash, task_uuid, task_title):
        self._task.proformatask_hash = hash
        self._task.proformatask_uuid = task_uuid
        self._task.proformatask_title = task_title

    def read_basic_attributes(self, xml_dict):
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


    def read_submission_restriction(self, xml_dict):
        path = ['submission-restrictions']
        max_size = None
        restriction = self.__getitem_from_dict(xml_dict, path)

        try:
            max_size = restriction.get("@max-size")
        except AttributeError:
            # no max size given => use default (1MB)
            max_size = 1000000

        # convert to KB
        self._task.max_file_size = int(max_size) / 1024

        # todo add file restrictions
        return True


class Task_2_00:
    format_namespace = "urn:proforma:v2.0"
    ns = {"p": format_namespace}

    # constructor
    def __init__(self, task_xml, xml_obj, hash, dict_zip_files=None):
        self.task_xml = task_xml
        self.xml_obj = xml_obj
        self.hash = hash
        self.dict_zip_files = dict_zip_files
        self.new_task = None
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
            raise TaskXmlException(msg + ' is missing')

        text = xmlTest.xpath(xpath, namespaces=namespaces)[0].text

        if text is None or len(text) == 0:
            raise TaskXmlException(msg + ' must not be empty')
        return text

#    def set_default_user(self, user_name):
#        try:
#            sys_user = User.objects.get(username=user_name)
#        except User.DoesNotExist:
#            sys_user = User.objects.create_user(username=user_name, email="creator@localhost")
#        #return sys_user


    # read all files from task and put them into a dictionary
    def __collect_files(self, xml_obj, external_file_dict=None, ):
        namespace = self.ns
        # Files create dict with internal file objects should also used for external files
        orphain_files = dict()
        # external_file_dict = dict()
        test_files = dict()
        modelsolution_files = dict()

        list_of_files = xml_obj.xpath("/p:task/p:files/p:file", namespaces=namespace)

        for k in list_of_files:
            # todo add: embedded-bin-file
            # todo add: attached-txt-file
            used_by_grader = k.attrib.get('used-by-grader')
            if used_by_grader == "true":
                if k.xpath("p:embedded-txt-file", namespaces=namespace):
                    t = tempfile.NamedTemporaryFile(delete=True)
                    t.write(k['embedded-txt-file'].text.encode("utf-8"))
                    t.flush()
                    my_temp = File(t)
                    my_temp.name = k['embedded-txt-file'].attrib.get("filename")
                    logger.debug('add file to dictionary: ' + k.attrib.get("id") + ' => ' + my_temp.name)
                    orphain_files[k.attrib.get("id")] = my_temp
                elif k.xpath("p:attached-bin-file", namespaces=namespace):
                    filename = k['attached-bin-file'].text
                    if external_file_dict is None:
                        raise Exception('no files in zip found')
                        #orphain_files[k.attrib.get("id")] = external_file_dict[filename]
                else:
                    raise Exception('unsupported file type in task.xml (embedded-bin-file or attached-txt-file)')

        logger.debug('all_files created')
        #from pprint import pprint
        #pprint(all_files)

        # List with all files that are referenced by tests
        list_of_test_files = xml_obj.xpath("/p:task/p:tests/p:test/p:test-configuration/"
                                           "p:filerefs/p:fileref/@refid", namespaces=namespace)
        # Remove duplicates from list (for files that are referenced by more than one test)!!
        list_of_test_files = list(dict.fromkeys(list_of_test_files))
        for test_ref_id in list_of_test_files:
            logger.debug('pop: ' + test_ref_id)
            test_ref_id_of_dict = {test_ref_id: orphain_files.pop(test_ref_id, "")}
            test_files.update(test_ref_id_of_dict)

        #logger.debug('test_files: ')
        #pprint(test_files)

        # model solution files should already be sorted out
        #list_of_modelsolution_refs_path = xml_obj.xpath("/p:task/"
        #                                                "p:model-solutions/p:model-solution/p:filerefs/"
        #                                                "p:fileref/@refid", namespaces=namespace)

        #for model_solution_id in list_of_modelsolution_refs_path:
        #    model_ref_id_of_dict = {model_solution_id: orphain_files.pop(model_solution_id, "")}
        #    modelsolution_files.update(model_solution_id=model_ref_id_of_dict)

        # dict of test_file_ids
        return orphain_files, test_files


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
    def __add_files_to_subtest(self, file_dict, xml_test, firstHandler = None, inst = None):
        order_counter = 1

        count = 0
        for fileref in xml_test.xpath("p:test-configuration/p:filerefs/p:fileref", namespaces=self.ns):
            refid = fileref.attrib.get("refid")
            reffile = file_dict.get(refid)
            if reffile is None:
                raise TaskXmlException('cannot find file with id = ' + refid)
            logger.debug('handle test file ' + reffile.name)
            if count == 0:
                if firstHandler is not None:
                    logger.debug('handle first test file ' + reffile.name)
                    firstHandler(inst, reffile)
                count = count +1
            else:
                logger.debug('create normal test file' + reffile.name)
                inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=self.new_task.praktomatTask,
                                                                           order=self.val_order,
                                                                           path=""
                                                                           )
                inst2.file = reffile # check if the refid is there
                if dirname(reffile.name) is not None:
                    inst2.path = dirname(reffile.name)
                inst2.always = True
                inst2.public = False
                inst2.required = False
                inst2.save()
                order_counter += 1
                self.val_order += 1  # to push the junit-checker behind create-file checkers
                logger.debug('__add_files_to_subtest: increment vald_order, new value= ' + str(self.val_order))
                inst.files.add(inst2)


    def __create_java_compiler_checker(self, xmlTest):
        inst = JavaBuilder.JavaBuilder.objects.create(task=self.new_task.praktomatTask,
                                                      order=self.val_order,
                                                      _flags="",
                                                      _output_flags="",
                                                      _file_pattern=r"^.*\.[jJ][aA][vV][aA]$",
                                                      _main_required=False
                                                      )

        self.__set_test_base_parameters(inst, xmlTest)
        inst.save()


    def __create_java_unit_checker(self, xmlTest, test_file_dict):
        checker_ns = self.ns.copy()
        checker_ns['unit_new'] = 'urn:proforma:tests:unittest:v1.1'
        checker_ns['unit'] = 'urn:proforma:tests:unittest:v1'

        inst = JUnitChecker.JUnitChecker.objects.create(task=self.new_task.praktomatTask, order=self.val_order)
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

        if xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=checker_ns):
            self.val_order = task.creating_file_checker(embedded_file_dict=test_file_dict, new_task=self.new_task.praktomatTask, ns=checker_ns,
                                              val_order=self.val_order, xml_test=xmlTest, checker=inst)

        inst.order = self.val_order
        inst.save()


    def __create_java_checkstyle_checker(self, xmlTest, test_files):
        checker_ns = self.ns.copy()
        checker_ns['check'] = 'urn:proforma:tests:java-checkstyle:v1.1'

        inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=self.new_task.praktomatTask, order=self.val_order)
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
        self.__add_files_to_subtest(test_files, xmlTest, set_mainfile, inst)
        inst.order = self.val_order
        inst.save()


    def __create_setlx_checker(self, xmlTest, test_files):
        inst = SetlXChecker.SetlXChecker.objects.create(task=self.new_task.praktomatTask, order=self.val_order)

        def set_mainfile(inst, value):
            inst.testFile = value
        self.__add_files_to_subtest(test_files, xmlTest, firstHandler=set_mainfile, inst=inst)
        self.__set_test_base_parameters(inst, xmlTest)
        inst.save()


    def __create_python_checker(self, xmlTest, test_files):
        inst = PythonChecker.PythonChecker.objects.create(task=self.new_task.praktomatTask, order=self.val_order)
        self.__set_test_base_parameters(inst, xmlTest)
        def set_mainfile(inst, value):
            inst.doctest = value
        self.__add_files_to_subtest(test_files, xmlTest, firstHandler=set_mainfile, inst=inst)
        inst.save()


    # todo???
    # proglang -> e.g Java 1.6 / Python 2.7
    # files : used-by-grader="true"

    # MAIN FUNCTION OF CLASS
    # model-solutions
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
        old_task = task.get_task(self.hash, task_uuid, task_title)
        if old_task != None:
            return old_task

        # no need to actually validate xml against xsd
        # (it is only time consuming)
        schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
        # todo: remove because it is very expensive (bom, about 350ms)
        # logger.debug('task_xml = ' + str(task_xml))
        t = tempfile.NamedTemporaryFile(delete=True)
        t.write(self.task_xml)  # todo: encoding
        t.flush()
        t.seek(0)

        self.xml_dict = schema.to_dict(t)

        # xml_dict = validate_xml(xml=task_xml)

        # xml_obj = objectify.fromstring(xml_object) # task_xml)

        self.new_task = Praktomat_Task_2_00()
        try:
            self.new_task.read_basic_attributes(self.xml_dict)
            self.new_task.read_submission_restriction(self.xml_dict)
            # self.set_default_user(user_name=SYSUSER)

            if self.dict_zip_files is None:
                orphain_files, test_files = self.__collect_files(xml_obj=self.xml_obj)
            else:
                orphain_files, test_files = self.__collect_files(xml_obj=self.xml_obj, external_file_dict=self.dict_zip_files)

            if len(orphain_files)> 0:
                logger.error('orphain files found: ' + str(orphain_files))

            # create files not refered by a test (# todo: invalid: raise exception)
            self.val_order = task.creatingFileCheckerNoDep(orphain_files, self.new_task.praktomatTask, self.ns,
                                                                             self.val_order, xmlTest=None)
            for xmlTest in self.xml_obj.tests.iterchildren():
                testtype = xmlTest.xpath("p:test-type", namespaces=self.ns)[0].text
                if testtype == "java-compilation":  # todo check compilation_xsd
                    logger.debug('** __create_java_compiler_checker')
                    self.__create_java_compiler_checker(xmlTest)
                elif testtype == "unittest":
                    logger.debug('** __create_java_unit_checker')
                    self.__create_java_unit_checker(xmlTest, test_files)
                elif testtype == "java-checkstyle":
                    self.__create_java_checkstyle_checker(xmlTest, test_files)
                elif testtype == "setlx": # and xmlTest.xpath("p:test-configuration/jartest:jartest[@framework='setlX']", namespaces=ns):
                    self.__create_setlx_checker(xmlTest, test_files)
                elif testtype == "python-doctest":
                    logger.debug('** __create_python_checker')
                    self.__create_python_checker(xmlTest, test_files)
                self.val_order += 1
                logger.debug('import_task/llop: increment vald_order, new value= ' + str(self.val_order))

        except Exception:
            self.new_task.delete()
            self.new_task = None
            raise

        self.new_task.set_identifier_values(self.hash, task_uuid, task_title)
        #self.new_task.proformatask_hash = self.hash
        #self.new_task.proformatask_uuid = task_uuid
        #self.new_task.proformatask_title = task_title
        self.new_task.save()
        return self.new_task.praktomatTask




    # @csrf_exempt  # disable csrf-cookie
    # def json_error_message(json_message, http_code=None):
    #     if http_code is None:
    #         return HttpResponse(content=json.dumps(json_message), status=400, content_type="application/json")
    #     else:
    #         return HttpResponse(content=json.dumps(json_message), status=http_code, content_type="application/json")


    # def validate_xml(xml, xml_version=None):
    #     if xml_version is None:
    #         schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
    #         #try:
    #         #    schema.validate(xml)
    #         #except Exception as e:
    #         #    logger.error("Schema is not valid: " + str(e))
    #         #    raise Exception("Schema is not valid: " + str(e))
    #     return schema.to_dict(xml)
