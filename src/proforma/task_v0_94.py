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

# functions for importing ProFormA tasks version 0.9.4 into Praktomat database.
# Version 0.9.4 is depricated, do not use anymore!!

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.core.files import File
from django.views.decorators.csrf import csrf_exempt

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
    JavaBuilder, DejaGnu, TextNotChecker, PythonChecker, RemoteSQLChecker, TextChecker, SetlXChecker


import task


logger = logging.getLogger(__name__)


def creatingFileChecker(embeddedFileDict, newTask, ns, valOrder, xmlTest):
    orderCounter = 1
    for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs/proforma:fileref", namespaces=ns):
        if embeddedFileDict.get(fileref.attrib.get("refid")) is not None:
            inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=newTask,
                                                                       order=valOrder,
                                                                       path=""
            )
            inst2.file = embeddedFileDict.get(fileref.attrib.get("refid")) #check if the refid is there
            if dirname(embeddedFileDict.get(fileref.attrib.get("refid")).name) is not None:
                inst2.path = dirname(embeddedFileDict.get(fileref.attrib.get("refid")).name)
            else:
                pass

            inst2 = task.testVisibility(inst2, xmlTest, ns, False)
            inst2.save()
            orderCounter += 1
            valOrder += 1  #to push the junit-checker behind create-file checkers
    return valOrder


def importTask(task_xml, dict_zip_files):
    """
    importTaskObject(request)
    return response

    url: importTaskObject
    expect xml-file in post-request
    tries to objectify the xml and import it in Praktomat
    """
    log = ""  # for hints could not imported
    RXCODING = re.compile(r"encoding=(\"|\')(?P<enc>[\w.-]+)")
    RXVERSION = re.compile(r"^(?P<major>(\d+))(\.){1}?(?P<minor>(\d+))(\.){1}?(\.|\d+)+$")
    DEFINED_USER = "sys_prod"
    message = ""
    response = HttpResponse()
    #the right ns is also for the right version necessary
    ns = {"proforma": "urn:proforma:task:v0.9.4",
          "praktomat": "urn:proforma:praktomat:v0.1",
          "unit": "urn:proforma:unittest",
          "jartest": 'urn:proforma:tests:jartest:v1',
          }
    #check_post_request(request)
    #filename, uploaded_file = request.FILES.popitem()  # returns list?

    # check ZIP
    #if filename[-3:].upper() == 'ZIP':
    #    task_xml, dict_zip_files = extract_zip_with_xml_and_zip_dict(uploaded_file=uploaded_file)
    #else:
    #    task_xml = uploaded_file[0].read()  # todo check name

    try:
        #encoding = chardet.detect(xmlExercise)['encoding'] # does not work perfectly
        encodingSearch = RXCODING.search(task_xml, re.IGNORECASE)
        if encodingSearch:
            encoding = encodingSearch.group("enc")

            if str(encoding).upper() != 'UTF-8':
                xmlExercise = task_xml.decode(encodingSearch.group('enc')).encode('utf-8')  # todo: remove decode
            else:
                pass
            #xmlExercise = xmlExercise.decode('utf-8', 'replace')
            #encXML = utf8_file.decode('utf-8', "xmlcharrefreplace")
            #encXML = utf8_file.decode('utf-8', "ignore")
        else:
            pass

        xmlObject = objectify.fromstring(task_xml)

    except Exception as e:
        response.write("Error while parsing xml\r\n" + str(e))
        return response

    #xmlTask = xmlObject.getroot()
    xmlTask = xmlObject
    # TODO check against schema
    # schemaObject = schemaToObject(fSchema)
    # xmlObject = validation(fXml, schemaObject)

    #check Namespace
    if not 'urn:proforma:task:v0.9.4' in xmlObject.nsmap.values():
        response.write("The Exercise could not be imported!\r\nOnly support for Namspace: urn:proforma:task:v0.9.4")
        return response

    #TODO datetime max?
    newTask = Task.objects.create(title="test", description=xmlTask.description.text, submission_date=datetime.now(), publication_date=datetime.now())
    if (xmlTask.xpath("proforma:submission-restrictions", namespaces=ns) is None) \
       or xmlTask.xpath("proforma:submission-restrictions", namespaces=ns) is False:
        newTask.delete()
        response.write("The Exercise could not be imported!\r\nsubmission-restrictions-Part is missing")
        return response
    else:
        if xmlTask.xpath("proforma:submission-restrictions", namespaces=ns)[0].attrib.get("max-size") is not None:
            newTask.max_file_size = int(xmlTask.xpath("proforma:submission-restrictions", namespaces=ns)[0].attrib.get("max-size"))
        else:
            newTask.max_file_size = 1000

        if (xmlTask.xpath("proforma:meta-data/praktomat:allowed-upload-filename-mimetypes",
                          namespaces=ns) and
            xmlTask.xpath("proforma:meta-data/praktomat:allowed-upload-filename-mimetypes",
                          namespaces=ns)[0].text):
            newTask.supported_file_types = xmlTask.xpath("proforma:meta-data/praktomat:allowed-upload-filename-mimetypes",
                                                         namespaces=ns)[0]
        else:
            newTask.supported_file_types = ".*"  # all

    # Files create dict with file objects
    embeddedFileDict = dict()
    for xmlFile in xmlTask.xpath("proforma:files/proforma:file", namespaces=ns):
        if xmlFile.attrib.get("class") == "internal" or xmlFile.attrib.get("class") == "instruction":
            t = tempfile.NamedTemporaryFile(delete=True)
            t.write(xmlFile.text.encode("utf-8"))
            t.flush()
            myT = File(t)
            myT.name = (xmlFile.attrib.get("filename"))  # check! basename? i lost the path..
            embeddedFileDict[xmlFile.attrib.get("id")] = myT  #warum id = int? soll doch string sein

    # Files create dict with file objects for library
    createFileDict = dict()
    for xmlFile in xmlTask.xpath("proforma:files/proforma:file", namespaces=ns):
        if (xmlFile.attrib.get("class") == "library") or (xmlFile.attrib.get("class") == "internal-library"):
            t = tempfile.NamedTemporaryFile(delete=True)
            t.write(xmlFile.text.encode("utf-8"))
            t.flush()
            myT = File(t)
            myT.name = (xmlFile.attrib.get("filename"))  # check! basename? i lost the path..
            createFileDict[xmlFile.attrib.get("id")] = myT  #warum id = int? soll doch string sein


    # check if sysuser is created
    try:
        sysProd = User.objects.get(username=DEFINED_USER)
    except Exception as e:
        newTask.delete()
        response.write("System User (" + DEFINED_USER + ") does not exist: " + str(e))
        return response

    #new model-solution import
    if xmlTask.xpath("proforma:model-solutions/proforma:model-solution", namespaces=ns):
        modelSolutions = xmlTask.xpath("proforma:model-solutions", namespaces=ns)
        # check files>file.id with model-solutions>model-solution>filerefs>fileref>refid
        # jeweils eine model solution
        for modelSolution in xmlTask.xpath("proforma:model-solutions/proforma:model-solution", namespaces=ns):
            try:
                solution = Solution(task=newTask, author=sysProd)
            except Exception as e:
                newTask.delete()
                response.write("Error while importing Solution: " + str(e))
                return response
            if modelSolution.xpath("proforma:filerefs", namespaces=ns):
                for fileRef in modelSolution.filerefs.iterchildren():
                    if fileRef.attrib.get("refid") in embeddedFileDict:
                        solution.save()
                        solutionFile = SolutionFile(solution=solution)
                        solutionFile.file = embeddedFileDict.get(fileRef.attrib.get("refid"))  #TODO check more than one solution
                        solutionFile.save()
                        newTask.model_solution = solution
                    else:
                        newTask.delete()
                        response.write("You reference a model-solution to the files but there is no refid!")
                        return response

    else:
        newTask.delete()
        response.write("No Model Solution attached")
        return response

    if xmlTask.xpath("proforma:meta-data/proforma:title", namespaces=ns):
        newTask.title = xmlTask.xpath("proforma:meta-data/proforma:title", namespaces=ns)[0].text
    else:
        xmlTask.title = "unknown exercise"

    valOrder = 1

    # create library and internal-library with create FileChecker
    valOrder = task.creatingFileCheckerNoDep(createFileDict, newTask, ns, valOrder, xmlTest=None)



    for xmlTest in xmlTask.tests.iterchildren():
        if xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "anonymity":
            inst = AnonymityChecker.AnonymityChecker.objects.create(task=newTask, order=valOrder)
            inst = task.testVisibility(inst, xmlTest, ns)
            inst.save()

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "java-compilation":
            inst = JavaBuilder.JavaBuilder.objects.create(task=newTask,
                                                          order=valOrder,
                                                          _flags="",
                                                          _output_flags="",
                                                          _file_pattern=r"^.*\.[jJ][aA][vV][aA]$"
                                                          )
            # first check if path exist, second if the element is empty
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFlags",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFlags",
                              namespaces=ns)[0].text is not None):
                inst._flags = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFlags",
                                            namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerOutputFlags",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerOutputFlags",
                              namespaces=ns)[0].text is not None):
                inst._output_flags = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                   "praktomat:config-CompilerOutputFlags",
                                                   namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerLibs",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerLibs",
                              namespaces=ns)[0].text):
                inst._libs = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerLibs",
                                           namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFilePattern",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFilePattern",
                              namespaces=ns)[0].text):
                inst._file_pattern = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                   "praktomat:config-CompilerFilePattern",
                                                   namespaces=ns)[0]
            try:
                inst = task.testVisibility(inst, xmlTest, ns)
            except Exception as e:
                newTask.delete()
                response.write("Error while parsing xml\r\n" + str(e))
                return response
            inst.save()

        #this one will not used anymore
        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-CreateFileChecker":
            for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):

                if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                    inst = CreateFileChecker.CreateFileChecker.objects.create(task=newTask,
                                                                              order=valOrder,
                                                                              path=""
                                                                              )
                    inst.file = embeddedFileDict.get(fileref.fileref.attrib.get("refid")) #check if the refid is there
                    if dirname(embeddedFileDict.get(fileref.fileref.attrib.get("refid")).name) is not None:
                        inst.path = dirname(embeddedFileDict.get(fileref.fileref.attrib.get("refid")).name)
                    inst = task.testVisibility(inst, xmlTest, ns)
                    inst.save(force_update=True)

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "dejagnu-setup":
            for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                    inst = DejaGnu.DejaGnuSetup.objects.create(task=newTask, order=valOrder)
                    inst.test_defs = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
                    inst = task.testVisibility(inst, xmlTest, ns)
                    inst.save()
                #todo else

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "dejagnu-tester":
            for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                    inst = DejaGnu.DejaGnuTester.objects.create(task=newTask, order=valOrder)
                    inst.test_case = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
                    if xmlTest.xpath("proforma:title", namespaces=ns)[0] is not None:
                        inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
                    inst = task.testVisibility(inst, xmlTest, ns)
                    inst.save()

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-TextNotChecker":
            fine = True
            inst = TextNotChecker.TextNotChecker.objects.create(task=newTask, order=valOrder)
            if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
                              namespaces=ns)[0].text):
                inst.text = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
                                          namespaces=ns)[0].text
            else:
                inst.delete()
                fine = False
                message = "TextNotChecker removed: no config-text"

            if (fine and xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                       "praktomat:config-max_occurrence",
                                       namespaces=ns) and
                    xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                  "praktomat:config-max_occurrence",
                                  namespaces=ns)[0].text):
                inst.max_occ = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                             "praktomat:config-max_occurrence",
                                             namespaces=ns)[0].text
            else:
                inst.delete()
                fine = False
                message = "TextNotChecker removed: no max_occurence"

            if fine:
                inst = task.testVisibility(inst, xmlTest, ns)
                inst.save()
            else:
                pass

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "textchecker":
            inst = TextChecker.TextChecker.objects.create(task=newTask, order=valOrder)
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/proforma:praktomat:config-text",
                              namespaces=ns)[0].text):
                inst.text = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
                                          namespaces=ns)[0].text
                if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
            else:
                inst.delete()
                message = "Textchecker removed: no config-text"

            inst = task.testVisibility(inst, xmlTest, ns)
            inst.save()
        #setlx with jartest
        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "jartest" and \
                xmlTest.xpath("proforma:test-configuration/jartest:jartest[@framework='setlX']", namespaces=ns):

            for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                    inst = SetlXChecker.SetlXChecker.objects.create(task=newTask, order=valOrder)
                    inst.testFile = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))

            if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]

            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
                              namespaces=ns)[0].text):
                inst.test_description = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                      "praktomat:config-testDescription",
                                                      namespaces=ns)[0].text

            inst = task.testVisibility(inst, xmlTest, ns)
            inst.save()

        #checkstyle with jartest todo:version-check check for valid regex
        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "jartest" and \
                xmlTest.xpath("proforma:test-configuration/jartest:jartest[@framework='checkstyle']", namespaces=ns):

            for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                    inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=newTask, order=valOrder)
                    inst.configuration = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
                if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
                if xmlTest.xpath("proforma:test-configuration/jartest:jartest/jartest:parameter",
                                 namespaces=ns) is not None:
                    paraList = list()
                    for parameter in xmlTest.xpath("proforma:test-configuration/jartest:jartest/jartest:parameter", namespaces=ns):
                        paraList.append(str(parameter))
                    regText = '|'.join(paraList)
                    is_valid = task.reg_check(regText)
                    if is_valid:
                        inst.regText = regText
                    else:
                        message = "no vaild regex for checkstyle: " + str(regText)
                if xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:max-checkstyle-warnings"
                                 , namespaces=ns) is not None:
                    inst.allowedWarnings = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:max-checkstyle-warnings"
                                 , namespaces=ns)[0]


                inst = task.testVisibility(inst, xmlTest, ns)
                inst.save()

            if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]

            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
                              namespaces=ns)[0].text):
                inst.test_description = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                      "praktomat:config-testDescription",
                                                      namespaces=ns)[0].text

            inst = task.testVisibility(inst, xmlTest, ns)
            inst.save()

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "unittest" and \
                xmlTest.xpath("proforma:test-configuration/unit:unittest[@framework='JUnit']", namespaces=ns):
            inst = JUnitChecker.JUnitChecker.objects.create(task=newTask, order=valOrder)

            if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]

            if (xmlTest.xpath("proforma:test-configuration/unit:unittest/unit:main-class",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/unit:unittest/unit:main-class",
                              namespaces=ns)[0].text):
                inst.class_name = xmlTest.xpath("proforma:test-configuration/unit:unittest/unit:main-class",
                                                namespaces=ns)[0].text
            else:
                inst.delete()
                message = "unittest main-class not found. Check your namespace"
                break

            if xmlTest.xpath("proforma:test-configuration/unit:unittest[@framework='JUnit']", namespaces=ns):
                if xmlTest.xpath("proforma:test-configuration/unit:unittest[@framework='JUnit']",
                                 namespaces=ns)[0].attrib.get("version"):
                    version = re.split('\.', xmlTest.xpath("proforma:test-configuration/"
                                                           "unit:unittest[@framework='JUnit']",
                                                           namespaces=ns)[0].attrib.get("version"))

                    if int(version[0]) == 3:
                        inst.junit_version = 'junit3'
                    elif int(version[0]) == 4:
                        inst.junit_version = 'junit4'
                    else:
                        inst.delete()
                        message = "JUnit-Version not known: " + str(version)
                        break

            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
                              namespaces=ns)[0].text):
                inst.test_description = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                      "praktomat:config-testDescription",
                                                      namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/"
                              "proforma:test-meta-data/praktomat:config-testname",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/"
                              "proforma:test-meta-data/praktomat:config-testname",
                              namespaces=ns)[0].text):
                inst.name = xmlTest.xpath("proforma:test-configuration/"
                                          "proforma:test-meta-data/praktomat:config-testname",
                                          namespaces=ns)[0].text
            if xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                valOrder = creatingFileChecker(embeddedFileDict, newTask, ns, valOrder, xmlTest)

            inst.order = valOrder
            inst = task.testVisibility(inst, xmlTest, ns)
            inst.save()

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "java-checkstyle":
            for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                    inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=newTask, order=valOrder)
                    inst.configuration = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
                if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
                    inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
                if xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:max-checkstyle-warnings"
                                 , namespaces=ns):
                    inst.allowedWarnings = xmlTest.xpath("proforma:test-configuration/"
                                                         "proforma:test-meta-data/"
                                                         "praktomat:max-checkstyle-warnings", namespaces=ns)[0]
                inst = task.testVisibility(inst, xmlTest, ns)
                inst.save()

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "python":
            inst = PythonChecker.PythonChecker.objects.create(task=newTask, order=valOrder)
            if (xmlTest.xpath("proforma:title", namespaces=ns) and
               xmlTest.xpath("proforma:title", namespaces=ns)[0].text):
                inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-remove-regex", namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-remove-regex",
                              namespaces=ns)[0].text):
                inst.remove = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                            "praktomat:config-remove-regex",
                                             namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-returnHtml",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-returnHtml",
                              namespaces=ns)[0].text):
                inst.public = task.str2bool(xmlTest.xpath("proforma:test-configuration/"
                                                     "proforma:test-meta-data/praktomat:config-returnHtml",
                                                     namespaces=ns)[0].text)
            if xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                    if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
                        inst.doctest = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
                        inst = task.testVisibility(inst, xmlTest, ns)
                        inst.save()
                    else:
                        inst.delete()
                        message = "No File for python-checker found"

        elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "RemoteScriptChecker":
            inst = RemoteSQLChecker.RemoteScriptChecker.objects.create(task=newTask, order=valOrder)
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-studentFilename",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-studentFilename",
                              namespaces=ns)[0].text):
                inst.solution_file_name = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                        "praktomat:config-studentFilename",
                                                        namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-studentSolutionFilename",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-studentSolutionFilename",
                              namespaces=ns)[0].text):
                inst.student_solution_file_name = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                                                                "praktomat:config-studentSolutionFilename",
                                                                namespaces=ns)[0].text
            if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-returnHtml",
                              namespaces=ns) and
                xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
                              "praktomat:config-returnHtml",
                              namespaces=ns)[0].text):
                inst.returns_html = task.str2bool(xmlTest.xpath("proforma:test-configuration/"
                                                           "proforma:test-meta-data/"
                                                           "praktomat:config-returnHtml",
                                                           namespaces=ns)[0].text)
            if xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
                valOrder = creatingFileChecker(embeddedFileDict, newTask, ns, valOrder, xmlTest)

            inst.order = valOrder
            inst = task.testVisibility(inst, xmlTest, ns)
            inst.save()

        else:
            message = "Following Test could not imported\n" + objectify.dump(xmlTest) + "\r\n"

        valOrder += 1
    newTask.save()
    response_data = dict()
    response_data['taskid'] = newTask.id
    response_data['message'] = message
    return response_data # HttpResponse(json.dumps(response_data), content_type="application/json")




# first version of 0.9.4

# @csrf_exempt
# def importTaskObject(request, task_xml, dict_zip_files_post=None):
#     """
#     importTaskObject(request)
#     return response
#
#     url: importTaskObject
#     expect xml-file in post-request
#     tries to objectify the xml and import it in Praktomat
#     """
#     log = ""  # for hints could not imported
#     #RXCODING = re.compile(r"encoding[=](\"[-\w.]+[\"])")
#     RXCODING = re.compile(r"encoding=\"(?P<enc>[\w.-]+)")
#     DEFINED_USER = "sys_prod"
#     message = ""
#     response = HttpResponse()
#     #the right ns is also for the right version necessary
#     ns = {'proforma': 'urn:proforma:task:v0.9.4',
#           'praktomat': 'urn:proforma:praktomat:v0.1',
#           'unit': 'urn:proforma:junittest3',
#           'unit2': 'urn:proforma:tests:unittest:v1',
#           'ju3': 'urn:proforma:tests:junit3:v0.1',
#           'ju4': 'urn:proforma:tests:junit4:v0.1'}
#
#     xmlExercise = task_xml
#
#     if dict_zip_files_post is None:
#         dict_zip_files = None
#     else:
#         dict_zip_files = dict_zip_files_post
#
#
#     try:
#         #encoding = chardet.detect(xmlExercise)['encoding'] # does not work perfectly
#         encoding = RXCODING.search(xmlExercise, re.IGNORECASE)
#         if (encoding != 'UFT-8' or encoding != 'utf-8') and encoding is not None:
#             xmlExercise = xmlExercise.decode(encoding.group('enc')).encode('utf-8')
#         #encXML = utf8_file.decode('utf-8', "xmlcharrefreplace")
#         #encXML = utf8_file.decode('utf-8', "ignore")
#         xmlObject = objectify.fromstring(xmlExercise)
#
#     except Exception as e:
#         response.write("Error while parsing xml\r\n" + str(e))
#         return response
#
#     #xmlTask = xmlObject.getroot()
#     xmlTask = xmlObject
#     # TODO check against schema
#     # schemaObject = schemaToObject(fSchema)
#     # xmlObject = validation(fXml, schemaObject)
#
#     #check Namespace
#     if not 'urn:proforma:task:v0.9.4' in xmlObject.nsmap.values():
#         response.write("The Exercise could not be imported!\r\nOnly support for Namspace: urn:proforma:task:v0.9.4")
#         return response
#
#     #TODO datetime max?
#     newTask = Task.objects.create(title="test", description=xmlTask.description.text, submission_date=datetime.now(), publication_date=datetime.now())
#     if (xmlTask.xpath("proforma:submission-restrictions", namespaces=ns) is None) \
#        or xmlTask.xpath("proforma:submission-restrictions", namespaces=ns) is False:
#         newTask.delete()
#         response.write("The Exercise could not be imported!\r\nsubmission-restrictions-Part is missing")
#         return response
#     else:
#         if xmlTask.xpath("proforma:submission-restrictions", namespaces=ns)[0].attrib.get("max-size") is not None:
#             newTask.max_file_size = int(xmlTask.xpath("proforma:submission-restrictions", namespaces=ns)[0].attrib.get("max-size"))
#         else:
#             newTask.max_file_size = 1000
#
#         if (xmlTask.xpath("proforma:meta-data/praktomat:allowed-upload-filename-mimetypes",
#                           namespaces=ns) and
#             xmlTask.xpath("proforma:meta-data/praktomat:allowed-upload-filename-mimetypes",
#                           namespaces=ns)[0].text):
#             newTask.supported_file_types = xmlTask.xpath("proforma:meta-data/praktomat:allowed-upload-filename-mimetypes",
#                                                          namespaces=ns)[0]
#         else:
#             newTask.supported_file_types = ".*"  # all
#
#     # Files create dict with file objects
#     embeddedFileDict = dict()
#     for xmlFile in xmlTask.xpath("proforma:files/proforma:file", namespaces=ns):
#         if xmlFile.attrib.get("class") == "internal" or xmlFile.attrib.get("class") == "instruction":
#             t = tempfile.NamedTemporaryFile(delete=True)
#             t.write(xmlFile.text.encode("utf-8"))
#             t.flush()
#             myT = File(t)
#             myT.name = (xmlFile.attrib.get("filename"))
#             embeddedFileDict[xmlFile.attrib.get("id")] = myT
#
#     CreateFileDict = dict()
#     for xmlFile in xmlTask.xpath("proforma:files/proforma:file", namespaces=ns):
#         if xmlFile.attrib.get("class") == "library" or xmlFile.attrib.get("class") == "inputdata":
#             t = tempfile.NamedTemporaryFile(delete=True)
#             t.write(xmlFile.text.encode("utf-8"))
#             t.flush()
#             myT = File(t)
#             myT.name = (xmlFile.attrib.get("filename"))
#             CreateFileDict[xmlFile.attrib.get("id")] = myT
#     # check if sysuser is created
#     try:
#         sysProd = User.objects.get(username=DEFINED_USER)
#     except Exception as e:
#         newTask.delete()
#         response.write("System User (" + DEFINED_USER + ") does not exist: " + str(e))
#         return response
#
#     #new model-solution import
#     if xmlTask.xpath("proforma:model-solutions/proforma:model-solution", namespaces=ns):
#         modelSolutions = xmlTask.xpath("proforma:model-solutions", namespaces=ns)
#         # check files>file.id with model-solutions>model-solution>filerefs>fileref>refid
#         # jeweils eine model solution
#         for modelSolution in xmlTask.xpath("proforma:model-solutions/proforma:model-solution", namespaces=ns):
#             try:
#                 solution = Solution(task=newTask, author=sysProd)
#             except Exception as e:
#                 newTask.delete()
#                 response.write("Error while importing Solution: " + str(e))
#                 return response
#             if modelSolution.xpath("proforma:filerefs", namespaces=ns) is not None:
#                 for fileRef in modelSolution.filerefs.iterchildren():
#                     if fileRef.attrib.get("refid") in embeddedFileDict:
#                         solution.save()
#                         solutionFile = SolutionFile(solution=solution)
#                         solutionFile.file = embeddedFileDict.get(fileRef.attrib.get("refid"))  #TODO check more than one solution
#                         solutionFile.save()
#                         newTask.model_solution = solution
#                     else:
#                         newTask.delete()
#                         response.write("You reference a model-solution to the files but there is no refid!")
#                         return response
#
#     else:
#         newTask.delete()
#         response.write("No Model Solution attached")
#         return response
#
#     if xmlTask.xpath("proforma:meta-data/proforma:title", namespaces=ns) is not None:
#         newTask.title = xmlTask.xpath("proforma:meta-data/proforma:title", namespaces=ns)[0].text
#     else:
#         xmlTask.title = "unknown exercise"
#     valOrder = 1
#     for xmlTest in xmlTask.tests.iterchildren():
#         if xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "anonymity":
#             inst = AnonymityChecker.AnonymityChecker.objects.create(task=newTask, order=valOrder)
#             inst = task.testVisibility(inst, xmlTest, ns)
#             inst.save()
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "java-compilation":
#             inst = JavaBuilder.JavaBuilder.objects.create(task=newTask,
#                                                           order=valOrder,
#                                                           _flags="",
#                                                           _output_flags="",
#                                                           _file_pattern=r"^.*\.[jJ][aA][vV][aA]$"
#                                                           )
#             # first check if path exist, second if the element is empty
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFlags",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFlags",
#                               namespaces=ns)[0].text is not None):
#                 inst._flags = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFlags",
#                                             namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerOutputFlags",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerOutputFlags",
#                               namespaces=ns)[0].text is not None):
#                 inst._output_flags = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                                    "praktomat:config-CompilerOutputFlags",
#                                                    namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerLibs",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerLibs",
#                               namespaces=ns)[0].text):
#                 inst._libs = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerLibs",
#                                            namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFilePattern",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-CompilerFilePattern",
#                               namespaces=ns)[0].text):
#                 inst._file_pattern = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                                    "praktomat:config-CompilerFilePattern",
#                                                    namespaces=ns)[0]
#             try:
#                 inst = task.testVisibility(inst, xmlTest, ns)
#             except Exception as e:
#                 newTask.delete()
#                 response.write("Error while parsing xml\r\n" + str(e))
#                 return response
#             inst.save()
#
#         #this one will not used anymore
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-CreateFileChecker":
#             for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
#
#                 if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
#                     inst = CreateFileChecker.CreateFileChecker.objects.create(task=newTask,
#                                                                               order=valOrder,
#                                                                               path=""
#                                                                               )
#                     inst.file = embeddedFileDict.get(fileref.fileref.attrib.get("refid")) #check if the refid is there
#                     if dirname(embeddedFileDict.get(fileref.fileref.attrib.get("refid")).name) is not None:
#                         inst.path = dirname(embeddedFileDict.get(fileref.fileref.attrib.get("refid")).name)
#                     inst = task.testVisibility(inst, xmlTest, ns)
#                     inst.save(force_update=True)
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "dejagnu-setup" or \
#                         xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-DejaGnuSetup":
#             for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
#                 if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
#                     inst = DejaGnu.DejaGnuSetup.objects.create(task=newTask, order=valOrder)
#                     inst.test_defs = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
#                     inst = task.testVisibility(inst, xmlTest, ns)
#                     inst.save()
#                 #todo else
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "dejagnu-tester" or \
#                 xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-DejaGnuTester":
#             for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
#                 if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
#                     inst = DejaGnu.DejaGnuTester.objects.create(task=newTask, order=valOrder)
#                     inst.test_case = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
#                     if xmlTest.xpath("proforma:title", namespaces=ns)[0] is not None:
#                         inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
#                     inst = task.testVisibility(inst, xmlTest, ns)
#                     inst.save()
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-TextNotChecker":
#             fine = True
#             inst = TextNotChecker.TextNotChecker.objects.create(task=newTask, order=valOrder)
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                               namespaces=ns)[0].text):
#                 inst.text = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                                           namespaces=ns)[0].text
#             else:
#                 inst.delete()
#                 fine = False
#                 message = ("TextNotChecker removed: no config-text")
#
#             if (fine and xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                        "praktomat:config-max_occurrence",
#                                        namespaces=ns) and
#                     xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                   "praktomat:config-max_occurrence",
#                                   namespaces=ns)[0].text):
#                 inst.max_occ = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                              "praktomat:config-max_occurrence",
#                                              namespaces=ns)[0].text
#             else:
#                 inst.delete()
#                 fine = False
#                 message = ("TextNotChecker removed: no max_occurence")
#
#             if fine:
#                 inst = task.testVisibility(inst, xmlTest, ns)
#                 inst.save()
#             else:
#                 pass
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "textchecker":
#             inst = TextChecker.TextChecker.objects.create(task=newTask, order=valOrder)
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/proforma:praktomat:config-text",
#                               namespaces=ns)[0].text):
#                 inst.text = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                                           namespaces=ns)[0].text
#             else:
#                 inst.delete()
#                 message = ("Textchecker removed: no config-text")
#
#             inst = task.testVisibility(inst, xmlTest, ns)
#             inst.save()
#         ##only for gate import
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "java-junittest3":
#             #xmlTest.register_namespace('foo', 'urn:proforma:junittest3')
#             inst = JUnitChecker.JUnitChecker.objects.create(task=newTask, order=valOrder,
#                                                             test_description="I need a test description",
#                                                             name="test name")
#
#             if (xmlTest.xpath("proforma:test-configuration/unit:main-class",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/unit:main-class",
#                               namespaces=ns)[0].text):
#                 inst.class_name = xmlTest.xpath("proforma:test-configuration/unit:main-class",
#                                                 namespaces=ns)[0].text
#
#             if (xmlTest.xpath("proforma:test-configuration/proforma:filerefs/proforma:fileref", namespaces=ns) and
#                     xmlTest.xpath("proforma:test-configuration/"
#                                   "proforma:filerefs/"
#                                   "proforma:fileref",
#                                   namespaces=ns)[0].text):
#                 # print embeddedFileDict.get(int(xmlTest.attrib.get("id")))
#                 # print xmlTest.xpath("test-configuration/filerefs/fileref")[0].text
#                 #todo create File checker
#                 inst.order = (valOrder + 1)
#                 inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=newTask,
#                                                                            order=valOrder,
#                                                                            path=""
#                                                                            )
#                 inst2.file = embeddedFileDict.get(xmlTest.attrib.get("id"))
#                 #print dirname(xmlTask.xpath("/task/files/file")[0].attrib.get("filename"))
#                 if dirname(xmlTask.xpath("/task/files/file")[0].attrib.get("filename")) is not "":
#                     inst2.path = dirname(xmlTask.xpath("/task/files/file")[0].attrib.get("filename")) #todo does not work in actual version
#                 inst2 = task.testVisibility(inst2, xmlTest)
#                 inst2.save()
#                 valOrder += 1
#             inst = task.testVisibility(inst, xmlTest, ns)
#             inst.save()
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "java-junit":
#             inst = JUnitChecker.JUnitChecker.objects.create(task=newTask, order=valOrder)
#
#             if (xmlTest.xpath("proforma:test-configuration/ju3:mainclass",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/ju3:mainclass",
#                               namespaces=ns)[0].text):
#                 inst.class_name = xmlTest.xpath("proforma:test-configuration/ju3:mainclass",
#                                                 namespaces=ns)[0].text
#                 inst.junit_version = "junit3"
#
#             if (xmlTest.xpath("proforma:test-configuration/ju4:mainclass",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/ju4:mainclass",
#                               namespaces=ns)[0].text):
#                 inst.class_name = xmlTest.xpath("proforma:test-configuration/ju4:mainclass",
#                                                 namespaces=ns)[0].text
#                 inst.junit_version = "junit4"
#
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-testDescription",
#                               namespaces=ns)[0].text):
#                 inst.test_description = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                                       "praktomat:config-testDescription",
#                                                       namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/"
#                               "proforma:test-meta-data/praktomat:config-testname",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/"
#                               "proforma:test-meta-data/praktomat:config-testname",
#                               namespaces=ns)[0].text):
#                 inst.name = xmlTest.xpath("proforma:test-configuration/"
#                                           "proforma:test-meta-data/praktomat:config-testname",
#                                           namespaces=ns)[0].text
#             if xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns) is not None:
#                 orderCounter = 1
#
#             for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs/proforma:fileref", namespaces=ns):
#                 if embeddedFileDict.get(fileref.attrib.get("refid")) is not None:
#                     inst2 = CreateFileChecker.CreateFileChecker.objects.create(task=newTask,
#                                                                                order=valOrder,
#                                                                                path=""
#                                                                                )
#                     inst2.file = embeddedFileDict.get(fileref.attrib.get("refid")) #check if the refid is there
#                     if dirname(embeddedFileDict.get(fileref.attrib.get("refid")).name) is not None:
#                         inst2.path = dirname(embeddedFileDict.get(fileref.attrib.get("refid")).name)
#                     else:
#                         pass
#
#                     inst2 = task.testVisibility(inst2, xmlTest, ns)
#                     inst2.save()
#                     orderCounter += 1
#                     valOrder += 1  #to push the junit-checker behind create-file checkers
#             inst.order = valOrder
#             inst = task.testVisibility(inst, xmlTest, ns)
#             inst.save()
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "java-checkstyle" or \
#                         xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "no-type-CheckStyleChecker":
#             for fileref in xmlTest.xpath("proforma:test-configuration/proforma:filerefs", namespaces=ns):
#                 if embeddedFileDict.get(fileref.fileref.attrib.get("refid")) is not None:
#                     inst = CheckStyleChecker.CheckStyleChecker.objects.create(task=newTask, order=valOrder)
#                     inst.configuration = embeddedFileDict.get(fileref.fileref.attrib.get("refid"))
#                 if xmlTest.xpath("proforma:title", namespaces=ns) is not None:
#                     inst.name = xmlTest.xpath("proforma:title", namespaces=ns)[0]
#                 if xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:max-checkstyle-warnings"
#                                  , namespaces=ns):
#                     inst.allowedWarnings = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:max-checkstyle-warnings"
#                                  , namespaces=ns)[0]
#                 inst = task.testVisibility(inst, xmlTest, ns)
#                 inst.save()
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "python":
#             inst = PythonChecker.PythonChecker.objects.create(task=newTask, order=valOrder)
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                               namespaces=ns)[0].text):
#                 inst.name = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-text",
#                                           namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-remove-regex",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-remove-regex",
#                               namespaces=ns)[0].text):
#                 inst.remove = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                             "praktomat:config-remove-regex",
#                                              namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-returnHtml",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/praktomat:config-returnHtml",
#                               namespaces=ns)[0].text):
#                 inst.public = str2bool(xmlTest.xpath("proforma:test-configuration/"
#                                                      "proforma:test-meta-data/praktomat:config-returnHtml",
#                                                      namespaces=ns)[0].text)
#                 if xmlTask.xpath("/proforma:task/proforma:files/proforma:file", namespaces=ns)[0].attrib.get("type") == "embedded":  # todo: test makes no sense
#                     inst.doctest = embeddedFileDict.get(int(xmlTest.attrib.get("id")))
#
#             inst = task.testVisibility(inst, xmlTest, ns)
#             inst.save()
#
#         elif xmlTest.xpath("proforma:test-type", namespaces=ns)[0] == "RemoteScriptChecker":
#             inst = RemoteSQLChecker.RemoteScriptChecker.objects.create(task=newTask, order=valOrder)
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-studentFilename",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-studentFilename",
#                               namespaces=ns)[0].text):
#                 inst.solution_file_name = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                                         "praktomat:config-studentFilename",
#                                                         namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-studentSolutionFilename",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-studentSolutionFilename",
#                               namespaces=ns)[0].text):
#                 inst.student_solution_file_name = xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                                                                 "praktomat:config-studentSolutionFilename",
#                                                                 namespaces=ns)[0].text
#             if (xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-returnHtml",
#                               namespaces=ns) and
#                 xmlTest.xpath("proforma:test-configuration/proforma:test-meta-data/"
#                               "praktomat:config-returnHtml",
#                               namespaces=ns)[0].text):
#                 inst.returns_html = str2bool(xmlTest.xpath("proforma:test-configuration/"
#                                                            "proforma:test-meta-data/"
#                                                            "praktomat:config-returnHtml",
#                                                            namespaces=ns)[0].text)
#                 if xmlTask.xpath("/proforma:task/proforma:files/proforma:file",
#                                  namespaces=ns)[0].attrib.get("type") == "embedded":  # todo: test makes no sense
#                     inst.solution_file = embeddedFileDict.get(int(xmlTest.attrib.get("id")))
#
#             inst = task.testVisibility(inst, xmlTest, ns)
#             inst.save()
#
#         else:
#             message = "Following Test could not imported\n" + objectify.dump(xmlTest) + "\r\n"
#
#         valOrder += 1
#     newTask.save()
#     response_data = dict()
#     response_data['taskid'] = newTask.id
#     response_data['message'] = message
#     return response_data #HttpResponse(json.dumps(response_data), content_type="application/json")
