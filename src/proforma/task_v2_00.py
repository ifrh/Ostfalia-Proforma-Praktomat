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
from checker.checker import CheckStyleChecker, JUnitChecker, PythonChecker, SetlXChecker, \
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

def get_optional_xml_attribute_text(xmlTest, xpath, attrib, namespaces):
    if xmlTest.xpath(xpath, namespaces=namespaces) is None:
        return ""

    try:
        return xmlTest.xpath(xpath, namespaces=namespaces)[0].attrib.get(attrib)
    except:
        return ""

def get_optional_xml_element_text(xmlTest, xpath, namespaces):
    try:
        if xmlTest.xpath(xpath, namespaces=namespaces) is not None:
            return xmlTest.xpath(xpath, namespaces=namespaces)[0].text
    except:
        return ""

def get_required_xml_element_text(xmlTest, xpath, namespaces, msg):
    if xmlTest.xpath(xpath, namespaces=namespaces) is None:
        raise TaskXmlException(msg + ' is missing')

    text = xmlTest.xpath(xpath, namespaces=namespaces)[0].text

    if text is None or len(text) == 0:
        raise TaskXmlException(msg + ' must not be empty')
    return text



def set_visibilty(instance):
    instance.always = True
    instance.public = True
    instance.required = False
    return instance




def set_task_description(xml_dict, new_task):
    xml_description = xml_dict.get("description")
    if xml_description is None:
        new_task.description = "No description"
    else:
        new_task.description = xml_description
    #new_task.save()



def set_task_title(xml_dict, new_task):
    xml_title = xml_dict.get("title")
    if xml_title is None:
        new_task.title = "No title"
    else:
        new_task.title = xml_title
    #new_task.save()


def set_default_user(user_name, new_task):
    try:
        sys_user = User.objects.get(username=user_name)
    except User.DoesNotExist:
        sys_user = User.objects.create_user(username=user_name, email="creator@localhost")
    #return sys_user


def create_file_dict_func(xml_obj, namespace, external_file_dict=None, ):
    # Files create dict with internal file objects should also used for external files
    embedded_file_dict = dict()
    # external_file_dict = dict()
    create_file_dict = dict()
    test_file_dict = dict()
    modelsolution_file_dict = dict()

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
                embedded_file_dict[k.attrib.get("id")] = my_temp
            elif k.xpath("p:attached-bin-file", namespaces=namespace):
                filename = k['attached-bin-file'].text
                if external_file_dict is None:
                    raise Exception('no files in zip found')
                embedded_file_dict[k.attrib.get("id")] = external_file_dict[filename]
            else:
                raise Exception('unsupported file type in task.xml (embedded-bin-file or attached-txt-file)')

    create_file_dict = embedded_file_dict

    list_of_test_files = xml_obj.xpath("/p:task/p:tests/p:test/p:test-configuration/"
                                       "p:filerefs/p:fileref/@refid", namespaces=namespace)
    for test_ref_id in list_of_test_files:
        test_ref_id_of_dict = {test_ref_id: create_file_dict.pop(test_ref_id, "")}
        test_file_dict.update(test_ref_id_of_dict)

    list_of_modelsolution_refs_path = xml_obj.xpath("/p:task/"
                                                    "p:model-solutions/p:model-solution/p:filerefs/"
                                                    "p:fileref/@refid", namespaces=namespace)

    for model_solution_id in list_of_modelsolution_refs_path:
        model_ref_id_of_dict = {model_solution_id: create_file_dict.pop(model_solution_id, "")}
        modelsolution_file_dict.update(model_solution_id=model_ref_id_of_dict)

    # dict of test_file_ids
    return create_file_dict, test_file_dict, modelsolution_file_dict


def set_test_base_parameters(inst, xmlTest, ns):
    if xmlTest.xpath("p:title", namespaces=ns) is not None:
        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0].text
    #if (xmlTest.xpath("p:title", namespaces=ns) and xmlTest.xpath("p:title", namespaces=ns)[0].text):
    #    inst.name = xmlTest.xpath("p:title", namespaces=ns)[0].text
    inst.test_description = get_optional_xml_element_text(xmlTest, "p:description", ns)
    inst.proforma_id = xmlTest.attrib.get("id")  # required attribute!!


def create_testfiles(file_dict, new_task, ns, val_order, xml_test, firstHandler = None, inst = None):
    order_counter = 1

    count = 0
    for fileref in xml_test.xpath("p:test-configuration/p:filerefs/p:fileref", namespaces=ns):
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
            inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=new_task,
                                                                       order=val_order,
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
            val_order += 1  # to push the junit-checker behind create-file checkers
            inst.files.add(inst2)            
    return val_order


def create_java_compiler_checker(xmlTest, val_order, new_task, ns):
    checker_ns = ns.copy()
    #checker_ns['praktomat'] = 'urn:proforma:praktomat:v0.2'

    inst = JavaBuilder.JavaBuilder.objects.create(task=new_task,
                                                  order=val_order,
                                                  _flags="",
                                                  _output_flags="",
                                                  _file_pattern=r"^.*\.[jJ][aA][vV][aA]$",
                                                  _main_required=False
                                                  )

    set_test_base_parameters(inst, xmlTest, ns)
    # first check if path exist, second if the element is empty, third import the value
    #if xmlTest.xpath("p:title", namespaces=ns) is not None:
    #        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]

    inst = set_visibilty(inst)
    inst.save()
    pass




def create_java_unit_checker(xmlTest, val_order, new_task, ns, test_file_dict):
    checker_ns = ns.copy()
    checker_ns['unit_new'] = 'urn:proforma:tests:unittest:v1.1'
    checker_ns['unit'] = 'urn:proforma:tests:unittest:v1'

    inst = JUnitChecker.JUnitChecker.objects.create(task=new_task, order=val_order)
    set_test_base_parameters(inst, xmlTest, ns)
    #if xmlTest.xpath("p:title", namespaces=ns) is not None:
    #        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
    #inst.test_description = geget_required_xml_element_textt_optional_xml_element_text(xmlTest, "p:description", ns)

    inst.class_name = get_required_xml_element_text(xmlTest,
        "p:test-configuration/unit_new:unittest/unit_new:entry-point", checker_ns, 'JUnit entrypoint')

    junit_version = ''
    if xmlTest.xpath("p:test-configuration/unit:unittest[@framework='JUnit']", namespaces=checker_ns):
        junit_version = get_optional_xml_attribute_text(xmlTest,
            "p:test-configuration/unit:unittest[@framework='JUnit']", "version", checker_ns)
    elif xmlTest.xpath("p:test-configuration/unit_new:unittest[@framework='JUnit']", namespaces=checker_ns):
        junit_version = get_optional_xml_attribute_text(xmlTest,
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
        val_order = task.creating_file_checker(embedded_file_dict=test_file_dict, new_task=new_task, ns=checker_ns,
                                          val_order=val_order, xml_test=xmlTest, checker=inst)

    inst.order = val_order
    inst = set_visibilty(inst)
    inst.save()


def create_java_checkstyle_checker(xmlTest, val_order, new_task, ns, test_file_dict):
    checker_ns = ns.copy()
    checker_ns['check'] = 'urn:proforma:tests:java-checkstyle:v1.1'

    inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=new_task, order=val_order)
    set_test_base_parameters(inst, xmlTest, ns)
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
    inst = set_visibilty(inst)

    def set_mainfile(inst, value):
        inst.configuration = value
    create_testfiles(test_file_dict, new_task, ns, val_order, xmlTest, set_mainfile, inst)
    inst.order = val_order
    inst.save()


def create_setlx_checker(xmlTest, val_order, new_task, ns, test_file_dict):
    inst = SetlXChecker.SetlXChecker.objects.create(task=new_task, order=val_order)

    def set_mainfile(inst, value):
        inst.testFile = value
    create_testfiles(test_file_dict, new_task, ns, val_order, xmlTest, firstHandler=set_mainfile, inst=inst)
    set_test_base_parameters(inst, xmlTest, ns)
    inst = set_visibilty(inst)
    inst.save()



def create_python_checker(xmlTest, val_order, new_task, ns, test_file_dict):
    inst = PythonChecker.PythonChecker.objects.create(task=new_task, order=val_order)
    set_test_base_parameters(inst, xmlTest, ns)
    def set_mainfile(inst, value):
        inst.doctest = value
    create_testfiles(test_file_dict, new_task, ns, val_order, xmlTest, firstHandler=set_mainfile, inst=inst)
    inst = set_visibilty(inst)
    inst.save()


# todo???
# proglang -> e.g Java 1.6 / Python 2.7
# files : used-by-grader="true"

# model-solutions
# tests
#   compiler
#   JUNIT
#   Checkstyle
def import_task(task_xml, xml_obj, hash, dict_zip_files=None):
    format_namespace = "urn:proforma:v2.0"
    ns = {"p": format_namespace}
    message = ""

    task_in_xml = xml_obj.xpath("/p:task", namespaces=ns)
    task_uuid = task_in_xml[0].attrib.get("uuid")
    logger.debug('uuid is ' + task_uuid)
    task_title = xml_obj.xpath("/p:task/p:title", namespaces=ns)[0]
    logger.debug('title is "' + task_title + '"')

    old_task = task.get_task(hash, task_uuid, task_title)
    if old_task != None:
        response_data = dict()
        response_data['taskid'] = old_task.id
        response_data['message'] = message
        return response_data

    # no need to actually validate xml against xsd
    # (it is only time consuming)
    schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
    # todo: remove because it is very expensive (bom, about 350ms)
    # logger.debug('task_xml = ' + str(task_xml))
    t = tempfile.NamedTemporaryFile(delete=True)
    t.write(task_xml)  # todo: encoding
    t.flush()
    t.seek(0)

    xml_dict = schema.to_dict(t)

    # xml_dict = validate_xml(xml=task_xml)

    # xml_obj = objectify.fromstring(xml_object) # task_xml)

    new_task = Task.objects.create(title="test",
                                   description="",
                                   submission_date=datetime.now(),
                                   publication_date=datetime.now())

    try:
        set_task_title(xml_dict=xml_dict, new_task=new_task)
        set_task_description(xml_dict=xml_dict, new_task=new_task)
        set_submission_restriction(xml_dict=xml_dict, new_task=new_task)
        set_default_user(user_name=SYSUSER, new_task=new_task)

        if dict_zip_files is None:
            create_file_dict, test_file_dict, list_of_modelsolution_refs_path = create_file_dict_func(xml_obj=xml_obj, namespace=ns)
        else:
            create_file_dict, test_file_dict, list_of_modelsolution_refs_path = create_file_dict_func(xml_obj=xml_obj, namespace=ns, external_file_dict=dict_zip_files)

        val_order = 1
        #inst = None
        # create library and internal-library with create FileChecker
        val_order = task.creatingFileCheckerNoDep(create_file_dict, new_task, ns,
                                                                         val_order, xmlTest=None)
        for xmlTest in xml_obj.tests.iterchildren():
            testtype = xmlTest.xpath("p:test-type", namespaces=ns)[0].text
            if testtype == "java-compilation":  # todo check compilation_xsd
                logger.debug('** create_java_compiler_checker')
                create_java_compiler_checker(xmlTest, val_order, new_task, ns)
            elif testtype == "unittest":
                logger.debug('** create_java_unit_checker')
                create_java_unit_checker(xmlTest, val_order, new_task, ns, test_file_dict)
            elif testtype == "java-checkstyle":
                create_java_checkstyle_checker(xmlTest, val_order, new_task, ns, test_file_dict)
            elif testtype == "setlx": # and xmlTest.xpath("p:test-configuration/jartest:jartest[@framework='setlX']", namespaces=ns):
                create_setlx_checker(xmlTest, val_order, new_task, ns, test_file_dict)
            elif testtype == "python-doctest":
                logger.debug('** create_python_checker')
                create_python_checker(xmlTest, val_order, new_task, ns, test_file_dict)
            val_order += 1
    except Exception:
        new_task.delete()
        raise

    new_task.proformatask_hash = hash
    new_task.proformatask_uuid = task_uuid
    new_task.proformatask_title = task_title
    new_task.save()
    response_data = dict()
    response_data['taskid'] = new_task.id
    response_data['message'] = message
    return response_data

def getitem_from_dict(dataDict, mapList):
    """Iterate nested dictionary"""
    return reduce(getitem, mapList, dataDict)




def set_submission_restriction(xml_dict, new_task):
    path = ['submission-restrictions']
    max_size = None
    restriction = getitem_from_dict(xml_dict, path)

    try:
        max_size = restriction.get("@max-size")
    except AttributeError:
        # no max size given => use default (1MB)
        max_size = 1000000

    # convert to KB
    new_task.max_file_size = int(max_size) / 1024

    #new_task.save()
    # todo add file restrictions
    return True


@csrf_exempt  # disable csrf-cookie
def json_error_message(json_message, http_code=None):
    if http_code is None:
        return HttpResponse(content=json.dumps(json_message), status=400, content_type="application/json")
    else:
        return HttpResponse(content=json.dumps(json_message), status=http_code, content_type="application/json")


# def validate_xml(xml, xml_version=None):
#     if xml_version is None:
#         schema = xmlschema.XMLSchema(os.path.join(PARENT_BASE_DIR, XSD_V_2_PATH))
#         #try:
#         #    schema.validate(xml)
#         #except Exception as e:
#         #    logger.error("Schema is not valid: " + str(e))
#         #    raise Exception("Schema is not valid: " + str(e))
#     return schema.to_dict(xml)
