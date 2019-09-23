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

# functions for importing ProFormA tasks version 1.0.1 into Praktomat database.
# Version 1.0.1 is depricated, do not use anymore!!



from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.core.files import File

from datetime import datetime
from lxml import objectify
import re
import tempfile
import logging
from os.path import dirname

from tasks.models import Task
from accounts.models import User
from solutions.models import Solution, SolutionFile
from checker import CreateFileChecker, CheckStyleChecker, JUnitChecker, AnonymityChecker, \
    JavaBuilder, DejaGnu, TextNotChecker, PythonChecker, RemoteSQLChecker, TextChecker, SetlXChecker, CBuilder


import task


logger = logging.getLogger(__name__)

def import_task(task_xml, dict_zip_files_post=None ):
    """
    :param request: request object for getting POST and GET
    :return: response

    expect xml-file in post-request
    tries to objectify the xml and import it in Praktomat
    """

    logger.debug('handle task version 1.0.1')
    # is_zip = False
    rxcoding = re.compile(r"encoding=\"(?P<enc>[\w.-]+)")
    # rxversion = re.compile(r"^(?P<major>(\d+))(\.){1}?(?P<minor>(\d+))(\.){1}?(\.|\d+)+$")
    defined_user = "sys_prod"
    message = ""

    xmlexercise = task_xml

    if dict_zip_files_post is None:
        dict_zip_files = None
    else:
        dict_zip_files = dict_zip_files_post

    response = HttpResponse()

    # here is the actual namespace for the version
    format_namespace = "urn:proforma:task:v1.0.1"

    # the right ns is also for the right version necessary
    ns = {"p": format_namespace,
          "praktomat": "urn:proforma:praktomat:v0.2",
          "unit": "urn:proforma:tests:unittest:v1",
          "jartest": 'urn:proforma:tests:jartest:v1',
          }

    encoding = rxcoding.search(xmlexercise, re.IGNORECASE)
    if (encoding != 'UFT-8' or encoding != 'utf-8') and encoding is not None:
        xmlexercise = xmlexercise.decode(encoding.group('enc')).encode('utf-8')
    xml_object = objectify.fromstring(xmlexercise)


    xml_task = xml_object
    # TODO check against schema

    # check Namespace
    if format_namespace not in xml_object.nsmap.values():
        raise Exception("The Exercise could not be imported!\r\nOnly support for Namspace: " + format_namespace)

    # TODO datetime max?

    new_task = Task.objects.create(title="test",
                                   description=xml_task.description.text,
                                   submission_date=datetime.now(),
                                   publication_date=datetime.now())

    try:
        # check for submission-restriction
        if xml_task.find("p:submission-restrictions", namespaces=ns) is None:
            raise Exception("The Exercise could not be imported!\r\nsubmission-restrictions-Part is missing")
        else:
            if xml_task.xpath("p:submission-restrictions/*[@max-size]", namespaces=ns):
                new_task.max_file_size = int(xml_task.xpath("p:submission-restrictions/*[@max-size]",
                                                            namespaces=ns)[0].attrib.get("max-size"))
            else:
                new_task.max_file_size = 1000

            if xml_task.xpath("p:meta-data/*[@mime-type-regexp]", namespaces=ns):
                new_task.supported_file_types = xml_task.xpath("p:meta-data/*[@mime-type-regexp]", namespaces=ns)[0]
            else:
                new_task.supported_file_types = ".*"  # all

        # check for embedded or external files

        # Files create dict with internal file objects should also used for external files
        embedded_file_dict = dict()
        # external_file_dict = dict()
        create_file_dict = dict()

        for uploaded_file in xml_task.xpath("p:files/p:file", namespaces=ns):
            if uploaded_file.attrib.get("class") == "internal":
                if uploaded_file.attrib.get("type") == "embedded":
                    t = tempfile.NamedTemporaryFile(delete=True)
                    t.write(uploaded_file.text.encode("utf-8"))
                    t.flush()
                    my_temp = File(t)
                    my_temp.name = (uploaded_file.attrib.get("filename"))
                    embedded_file_dict[uploaded_file.attrib.get("id")] = my_temp
                else:
                    embedded_file_dict[uploaded_file.attrib.get("id")] = \
                        dict_zip_files[uploaded_file.attrib.get("filename")]

            # all files in this dict were created by CreateFileChecker
            if (uploaded_file.attrib.get("class") == "library") or \
               (uploaded_file.attrib.get("class") == "internal-library"):
                if uploaded_file.attrib.get("type") == "embedded":
                    t = tempfile.NamedTemporaryFile(delete=True)
                    t.write(uploaded_file.text.encode("utf-8"))
                    t.flush()
                    my_temp = File(t)
                    my_temp.name = (uploaded_file.attrib.get("filename"))  # check! basename? i lost the path o not?
                    create_file_dict[uploaded_file.attrib.get("id")] = my_temp
                else:
                    create_file_dict[uploaded_file.attrib.get("id")] = dict_zip_files[uploaded_file.attrib.get("filename")]
            # if uploaded_file.attrib.get("type") == "file" and is_zip:
            #     # 1. check filename with zip_dict -> ID zuweisen
            #     # elif uploaded_file.attrib.get("class") == "internal":
            #     # embedded_file_dict[uploaded_file.attrib.get("id")] = zip_file_object.
            #     for zip_filename in zip_dict:
            #         if uploaded_file.attrib.get("filename") == zip_filename:
            #             if (uploaded_file.attrib.get("class") == "library") or \
            #                     (uploaded_file.attrib.get("class") == "internal-library"):
            #                 create_file_dict[uploaded_file.attrib.get("id")] = zipFileName.key  # get value of key!
            #             elif uploaded_file.attrib.get("class") == "internal":
            #                 #  embedded_file_dict[uploaded_file.attrib.get("id")] = zip_file_object  #todo this will fail
            #                 pass
            #             else:
            #                 new_task.delete()
            #                 response.write("file class in task.xml is not known")
            #                 return response
            #         else:
            #             new_task.delete()
            #             response.write("content of zip is not referenced by task.xml")
            #             return response

        # check if sysuser is created
        try:
            sys_user = User.objects.get(username=defined_user)
        except Exception as e:
            raise Exception("System User (" + defined_user + ") does not exist: " + str(e))

        # check UUID
        if xml_task.xpath("/p:task/@uuid", namespaces=ns):
            pass
        else:
            raise Exception("No uuid")
        # new model-solution import
        if xml_task.xpath("p:model-solutions/p:model-solution", namespaces=ns):

            # check files > file.id with model-solutions > model-solution > filerefs > fileref > refid
            for modelSolution in xml_task.xpath("p:model-solutions/p:model-solution", namespaces=ns):
                try:
                    solution = Solution(task=new_task, author=sys_user)
                except Exception as e:
                    raise Exception("Error while importing Solution: " + str(e))

                # TODO check more than one solution
                if modelSolution.xpath("p:filerefs", namespaces=ns):
                    for fileRef in modelSolution.filerefs.iterchildren():
                        if fileRef.attrib.get("refid") in embedded_file_dict:
                            solution.save()
                            solution_file = SolutionFile(solution=solution)
                            solution_file.file = embedded_file_dict.get(fileRef.attrib.get("refid"))
                            solution_file.save()
                            new_task.model_solution = solution
                        else:
                            raise Exception("You reference a model-solution to the files but there is no refid!")
        else:
            raise Exception("No Model Solution attached")

        # task name
        if xml_task.xpath("p:meta-data/p:title", namespaces=ns):
            new_task.title = xml_task.xpath("p:meta-data/p:title", namespaces=ns)[0].text
        else:
            xml_task.title = "unknown exercise"

        val_order = 1
        inst = None
        # create library and internal-library with create FileChecker
        val_order = task.creatingFileCheckerNoDep(create_file_dict, new_task, ns,
                                                                         val_order, xmlTest=None)

        for xmlTest in xml_task.tests.iterchildren():

            if xmlTest.xpath("p:test-type", namespaces=ns)[0] == "anonymity":
                inst = AnonymityChecker.AnonymityChecker.objects.create(task=new_task, order=val_order)
                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "c-compilation":
                inst = CBuilder.CBuilder.objects.create(task=new_task,
                                                        order=val_order,
                                                        _flags="-Wall",
                                                        _output_flags="-o %s",
                                                        _file_pattern=r"^[a-zA-Z0-9_]*\.[cC]$"
                                                        )
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFlags",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFlags",
                                  namespaces=ns)[0].text is not None):
                    inst._flags = xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFlags",
                                                namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerOutputFlags",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerOutputFlags",
                                  namespaces=ns)[0].text is not None):
                    inst._output_flags = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                       "praktomat:config-CompilerOutputFlags",
                                                       namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerLibs",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerLibs",
                                  namespaces=ns)[0].text):
                    inst._libs = xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerLibs",
                                               namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFilePattern",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFilePattern",
                                  namespaces=ns)[0].text):
                    inst._file_pattern = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                       "praktomat:config-CompilerFilePattern",
                                                       namespaces=ns)[0]
                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "java-compilation":
                inst = JavaBuilder.JavaBuilder.objects.create(task=new_task,
                                                              order=val_order,
                                                              _flags="",
                                                              _output_flags="",
                                                              _file_pattern=r"^.*\.[jJ][aA][vV][aA]$"
                                                              )
                if xmlTest.attrib is not None:
                    attributes = xmlTest.attrib
                    if attributes.get("id"):
                        inst.proforma_id = attributes.get("id")
                # first check if path exist, second if the element is empty, third import the value
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFlags",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFlags",
                                  namespaces=ns)[0].text is not None):
                    inst._flags = xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFlags",
                                                namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerOutputFlags",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerOutputFlags",
                                  namespaces=ns)[0].text is not None):
                    inst._output_flags = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                       "praktomat:config-CompilerOutputFlags",
                                                       namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerLibs",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerLibs",
                                  namespaces=ns)[0].text):
                    inst._libs = xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerLibs",
                                               namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFilePattern",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-CompilerFilePattern",
                                  namespaces=ns)[0].text):
                    inst._file_pattern = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                       "praktomat:config-CompilerFilePattern",
                                                       namespaces=ns)[0]
                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "dejagnu-setup":
                for fileref in xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    if embedded_file_dict.get(fileref.fileref.attrib.get("refid")) is not None:
                        inst = DejaGnu.DejaGnuSetup.objects.create(task=new_task, order=val_order)
                        inst.test_defs = embedded_file_dict.get(fileref.fileref.attrib.get("refid"))
                        inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                        inst.save()
                    # todo else

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "dejagnu-tester":
                for fileref in xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    if embedded_file_dict.get(fileref.fileref.attrib.get("refid")) is not None:
                        inst = DejaGnu.DejaGnuTester.objects.create(task=new_task, order=val_order)
                        inst.test_case = embedded_file_dict.get(fileref.fileref.attrib.get("refid"))
                        if xmlTest.xpath("p:title", namespaces=ns)[0] is not None:
                            inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
                        inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                        inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "no-type-TextNotChecker":
                fine = True
                inst = TextNotChecker.TextNotChecker.objects.create(task=new_task, order=val_order)
                if xmlTest.xpath("p:title", namespaces=ns) is not None:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-text",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-text",
                                  namespaces=ns)[0].text):
                    inst.text = xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-text",
                                              namespaces=ns)[0].text
                else:
                    inst.delete()
                    fine = False
                    message = "TextNotChecker removed: no config-text"

                if (fine and xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                           "praktomat:config-max_occurrence",
                                           namespaces=ns) and
                        xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                      "praktomat:config-max_occurrence",
                                      namespaces=ns)[0].text):
                    inst.max_occ = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                 "praktomat:config-max_occurrence",
                                                 namespaces=ns)[0].text
                else:
                    inst.delete()
                    fine = False
                    message = "TextNotChecker removed: no max_occurence"

                if fine:
                    inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                    inst.save()
                else:
                    pass

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "textchecker":
                inst = TextChecker.TextChecker.objects.create(task=new_task, order=val_order)
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-text",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/p:praktomat:config-text",
                                  namespaces=ns)[0].text):
                    inst.text = xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-text",
                                              namespaces=ns)[0].text
                    if xmlTest.xpath("p:title", namespaces=ns) is not None:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
                else:
                    inst.delete()
                    message = "Textchecker removed: no config-text"

                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            # setlx with jartest
            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "jartest" and \
                    xmlTest.xpath("p:test-configuration/jartest:jartest[@framework='setlX']", namespaces=ns):

                for fileref in xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    if embedded_file_dict.get(fileref.fileref.attrib.get("refid")) is not None:
                        inst = SetlXChecker.SetlXChecker.objects.create(task=new_task, order=val_order)
                        inst.testFile = embedded_file_dict.get(fileref.fileref.attrib.get("refid"))

                if xmlTest.xpath("p:title", namespaces=ns) is not None:
                    if inst is None:
                        message = "Error in JARTest"
                        break
                    else:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]

                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-testDescription",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-testDescription",
                                  namespaces=ns)[0].text):
                    inst.test_description = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                          "praktomat:config-testDescription",
                                                          namespaces=ns)[0].text

                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            # checkstyle with jartest todo:version-check check for valid regex

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "jartest" and \
                    xmlTest.xpath("p:test-configuration/jartest:jartest[@framework='checkstyle']", namespaces=ns):

                for fileref in xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    if embedded_file_dict.get(fileref.fileref.attrib.get("refid")) is not None:
                        inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=new_task, order=val_order)
                        inst.configuration = embedded_file_dict.get(fileref.fileref.attrib.get("refid"))
                    if xmlTest.xpath("p:title", namespaces=ns) is not None:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
                    if xmlTest.xpath("p:test-configuration/jartest:jartest/jartest:parameter",
                                     namespaces=ns) is not None:
                        para_list = list()
                        for parameter in xmlTest.xpath("p:test-configuration/jartest:jartest/"
                                                       "jartest:parameter", namespaces=ns):
                            para_list.append(str(parameter))
                        reg_text = '|'.join(para_list)
                        is_valid = task.reg_check(reg_text)
                        if is_valid:
                            inst.regText = reg_text
                        else:
                            message = "no vaild regex for checkstyle: " + str(reg_text)
                    if xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                     "praktomat:max-checkstyle-warnings", namespaces=ns) is not None:
                        inst.allowedWarnings = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                             "praktomat:max-checkstyle-warnings", namespaces=ns)[0]

                    inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                    inst.save()

                if xmlTest.xpath("p:title", namespaces=ns) is not None:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]

                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-testDescription",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-testDescription",
                                  namespaces=ns)[0].text):
                    inst.test_description = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                          "praktomat:config-testDescription",
                                                          namespaces=ns)[0].text

                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "unittest" and \
                    xmlTest.xpath("p:test-configuration/unit:unittest[@framework='JUnit']", namespaces=ns):
                inst = JUnitChecker.JUnitChecker.objects.create(task=new_task, order=val_order)

                if xmlTest.attrib is not None:
                    attributes = xmlTest.attrib
                    if attributes.get("id"):
                        inst.proforma_id = attributes.get("id")

                if xmlTest.xpath("p:title", namespaces=ns) is not None:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]

                if (xmlTest.xpath("p:test-configuration/unit:unittest/unit:main-class",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/unit:unittest/unit:main-class",
                                  namespaces=ns)[0].text):
                    inst.class_name = xmlTest.xpath("p:test-configuration/unit:unittest/unit:main-class",
                                                    namespaces=ns)[0].text
                else:
                    inst.delete()
                    message = "unittest main-class not found. Check your namespace"
                    break

                if xmlTest.xpath("p:test-configuration/unit:unittest[@framework='JUnit']", namespaces=ns):
                    if xmlTest.xpath("p:test-configuration/unit:unittest[@framework='JUnit']",
                                     namespaces=ns)[0].attrib.get("version"):
                        version = re.split('\.', xmlTest.xpath("p:test-configuration/"
                                                               "unit:unittest[@framework='JUnit']",
                                                               namespaces=ns)[0].attrib.get("version"))

                        if int(version[0]) == 3:
                            inst.junit_version = 'junit3'
                        elif int(version[0]) == 4:
                            if str(version[1]) == "12-gruendel":
                                inst.junit_version = 'junit4.12-gruendel'
                            elif str(version[1]) == "12":
                                inst.junit_version = 'junit4.12'
                            else:
                                inst.junit_version = 'junit4'
                        else:
                            inst.delete()
                            message = "JUnit-Version not known: " + str(version)
                            break

                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-testDescription",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-testDescription",
                                  namespaces=ns)[0].text):
                    inst.test_description = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                          "praktomat:config-testDescription",
                                                          namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/"
                                  "p:test-meta-data/praktomat:config-testname",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/"
                                  "p:test-meta-data/praktomat:config-testname",
                                  namespaces=ns)[0].text):
                    inst.name = xmlTest.xpath("p:test-configuration/"
                                              "p:test-meta-data/praktomat:config-testname",
                                              namespaces=ns)[0].text
                if xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    val_order = task.creating_file_checker(embedded_file_dict=embedded_file_dict, new_task=new_task, ns=ns,
                                                      val_order=val_order, xml_test=xmlTest)

                inst.order = val_order
                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "java-checkstyle":
                for fileref in xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    if embedded_file_dict.get(fileref.fileref.attrib.get("refid")) is not None:
                        inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=new_task, order=val_order)
                        inst.configuration = embedded_file_dict.get(fileref.fileref.attrib.get("refid"))
                    if xmlTest.xpath("p:title", namespaces=ns) is not None:
                        inst.name = xmlTest.xpath("p:title", namespaces=ns)[0]
                    if xmlTest.attrib is not None:
                        attributes = xmlTest.attrib
                        if attributes.get("id"):
                            inst.proforma_id = attributes.get("id")
                    if xmlTest.xpath("p:test-configuration/praktomat:version", namespaces=ns):
                        checkstyle_version = re.split('\.', xmlTest.xpath("p:test-configuration/"
                                                      "praktomat:version", namespaces=ns)[0].text)
                        if int(checkstyle_version[0]) == 7 and int(checkstyle_version[1]) == 6:
                            inst.check_version = 'check-7.6'
                        elif int(checkstyle_version[0]) == 6 and int(checkstyle_version[1]) == 2:
                            inst.check_version = 'check-6.2'
                        elif int(checkstyle_version[0]) == 5 and int(checkstyle_version[1]) == 4:
                            inst.check_version = 'check-5.4'
                        else:
                            inst.delete()
                            message = "Checkstyle-Version is not supported: " + str(checkstyle_version)
                            break

                    if xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                     "praktomat:max-checkstyle-warnings", namespaces=ns):
                        inst.allowedWarnings = xmlTest.xpath("p:test-configuration/"
                                                             "p:test-meta-data/"
                                                             "praktomat:max-checkstyle-warnings", namespaces=ns)[0]
                    if xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                     "praktomat:max-checkstyle-errors", namespaces=ns):
                        inst.allowedErrors = xmlTest.xpath("p:test-configuration/"
                                                           "p:test-meta-data/"
                                                           "praktomat:max-checkstyle-errors", namespaces=ns)[0]
                    inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                    inst.save()

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "python":
                inst = PythonChecker.PythonChecker.objects.create(task=new_task, order=val_order)
                if (xmlTest.xpath("p:title", namespaces=ns) and
                   xmlTest.xpath("p:title", namespaces=ns)[0].text):
                    inst.name = xmlTest.xpath("p:title", namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-remove-regex", namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-remove-regex",
                                  namespaces=ns)[0].text):
                    inst.remove = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                "praktomat:config-remove-regex", namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-returnHtml",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/praktomat:config-returnHtml",
                                  namespaces=ns)[0].text):
                    inst.public = task.str2bool(xmlTest.xpath("p:test-configuration/"
                                                               "p:test-meta-data/"
                                                               "praktomat:config-returnHtml", namespaces=ns)[0].text)
                if xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    for fileref in xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                        if embedded_file_dict.get(fileref.fileref.attrib.get("refid")) is not None:
                            inst.doctest = embedded_file_dict.get(fileref.fileref.attrib.get("refid"))
                            inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                            inst.save()
                        else:
                            inst.delete()
                            message = "No File for python-checker found"

            elif xmlTest.xpath("p:test-type", namespaces=ns)[0] == "RemoteScriptChecker":
                inst = RemoteSQLChecker.RemoteScriptChecker.objects.create(task=new_task, order=val_order)
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-studentFilename",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-studentFilename",
                                  namespaces=ns)[0].text):
                    inst.solution_file_name = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                            "praktomat:config-studentFilename",
                                                            namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-studentSolutionFilename",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-studentSolutionFilename",
                                  namespaces=ns)[0].text):
                    inst.student_solution_file_name = xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                                                    "praktomat:config-studentSolutionFilename",
                                                                    namespaces=ns)[0].text
                if (xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-returnHtml",
                                  namespaces=ns) and
                    xmlTest.xpath("p:test-configuration/p:test-meta-data/"
                                  "praktomat:config-returnHtml",
                                  namespaces=ns)[0].text):
                    inst.returns_html = task.str2bool(xmlTest.xpath("p:test-configuration/"
                                                                     "p:test-meta-data/"
                                                                     "praktomat:config-returnHtml",
                                                                     namespaces=ns)[0].text)
                if xmlTest.xpath("p:test-configuration/p:filerefs", namespaces=ns):
                    val_order = task.creating_file_checker(embedded_file_dict, new_task, ns, val_order, xmlTest)

                inst.order = val_order
                inst = task.check_visibility(inst=inst, namespace=ns, xml_test=xmlTest)
                inst.save()

            else:
                message = "Following Test could not imported\n" + objectify.dump(xmlTest) + "\r\n"


            # todo handle this properly!
            if inst != None and xmlTest.attrib is not None:
                attributes = xmlTest.attrib
                if attributes.get("id"):
                    inst.proforma_id = attributes.get("id")
                    inst.save()

            val_order += 1
    except Exception:
        new_task.delete()
        raise

    new_task.save()
    response_data = dict()
    response_data['taskid'] = new_task.id
    response_data['message'] = message
    return response_data # HttpResponse(json.dumps(response_data), content_type="application/json")
