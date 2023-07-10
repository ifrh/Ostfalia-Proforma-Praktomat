# -*- coding: utf-8 -*-

# This file is part of Ostfalia-Praktomat.
#
# Copyright (C) 2012-2020 Ostfalia University (eCULT-Team)
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
# functions for grading a student's submission

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files import File

from accounts.models import User
from solutions.models import Solution, SolutionFile
from VERSION import version

from django.template.loader import render_to_string
from checker.checker.ProFormAChecker import ProFormAChecker

import os
import logging


logger = logging.getLogger(__name__)

keep_sandbox = False
if keep_sandbox:
    print('*********************************************\n')
    print('*** Attention! Sandboxes are not deleted! ***\n')
    print('*********************************************\n')


class Grader:
    def __init__(self, proformatask, namespace = None):
        self._proformatask = proformatask
        self.result = None
        self.solution = None
        self.namespace = namespace


    def _save_solution(self, fileDict, version_control = None):
        # solution object for submission
        logger.debug("save solution")

        DEFINED_USER = "sys_prod"
        self.solution = Solution(task=self._proformatask, author=User.objects.get(username=DEFINED_USER))
        # save the solution model in the database
        self.solution.save()

        for index in range(len(fileDict)):
            # create solution_file
            solution_file = SolutionFile(solution=self.solution)

            #save solution in enviroment and get the path
            filename = list(fileDict.keys())[index]
            #logger.debug('save file ' + filename)
            #logger.debug('-> save file ' + filename + ': <' + str(fileDict.values()[index]) + '>')
            data = list(fileDict.values())[index]
            saved_solution = _save_file(data, solution_file, filename)
            #remove the upload path
            shorter_saved_solution = saved_solution[len(settings.UPLOAD_ROOT):]  # todo besser +1 und doku
            #remove the beginnning slash -> relative path
            super_short_solution = shorter_saved_solution[1:]
            #save solution file
            solution_file.file = super_short_solution
            solution_file.save()

        if version_control != None:
            self.solution.versioncontrol = version_control


    def grade(self, fileDict, version_control, subtest_results):
        self.solution_files = fileDict
        self._save_solution(fileDict, version_control)
        logger.debug("grade solution")
        #start the checking process
        if settings.DETAILED_UNITTEST_OUTPUT:
            ProFormAChecker.retrieve_subtest_results = subtest_results
        else:
            ProFormAChecker.retrieve_subtest_results = False

        ProFormAChecker.xml_namespace = self.namespace
        yield from self.solution.check_solution(True, keep_sandbox)
        logger.debug('get results...')
        self.result = self.solution.allCheckerResults()


    def get_result(self, response_template, remove_CopyFileChecker = True):
        #fileNameList = []
        #fileNameList.append("submission.zip")
        logger.debug("create response with " + response_template)
        lcxml = self._get_solution_xml(self.solution_files, response_template, remove_CopyFileChecker)

        logger.debug("file_grader_post finished")

        return lcxml

    def __del__(self):
        # logger.debug("delete")
        if self.solution is not None:
            self.solution.delete()
            self.solution = None


    def _get_solution_xml(self, file_name, response_template, remove_CopyFileChecker):
        result = self.result
        solution = self.solution
        # have to set it manually because it will only check visible tests
        false_required_hidden_test = False
        solution.seperate = True
        from datetime import datetime
        solution.timestamp = datetime.now().isoformat()

        # solution.versioncontrol = True
        grader = dict()
        grader.update({"name": "praktomat"})
        grader.update({"version": version})


        for index in range(len(result)):
            if result[index].checker.required and not result[index].checker.public:
                if not result[index].passed:
                    solution.accepted = False
                    false_required_hidden_test = True
            logger.debug("Checker " + str(result[index].checker.order) + ": " + str(result[index].checker))

        # remove 'None' tests from proforma2
        res_arr = list(result)
        max = len(res_arr) - 1
        for index in range(len(res_arr)):
            indexReverse = max - index
            if not hasattr(res_arr[indexReverse].checker, 'proforma_id') and remove_CopyFileChecker:
                # CopyFile checker has no attribute passed!
                if not res_arr[indexReverse].passed:
                #    # todo if fail add Error-Message
                    logger.error('Checker None FAILED!')
                else:
                    logger.debug("remove Checker: " + str(res_arr[indexReverse].checker))
                    res_arr.remove(res_arr[indexReverse])


        logger.debug("Remaining Checkers: ")
        for index in range(len(res_arr)):
            logger.debug("Checker: " + str(res_arr[index].checker))

        response_xml = render_to_string(response_template,
                           {"solution": solution,
                            "testResultList": res_arr if remove_CopyFileChecker else result,
                            "fileName": file_name,
                            "grader": grader,
                            "namespace": self.namespace,
                            "required_hidden": false_required_hidden_test})

        return response_xml




def _save_file(data, solution_file, filename):
    """

    :param data:
    :param solution_file:
    :param filename:
    """

    solution_file.mime_type = _get_mimetype(
        filename)  # just define it it will be tested later todo: method wo es passiert
    solution = solution_file.solution
    full_directory = settings.UPLOAD_ROOT + '/SolutionArchive/Task_' + str(
        solution.task.id) + '/User_' + solution.author.username + '/Solution_' + str(
        solution.id) + '/'      # directory structure from solution.model
    full_filename = os.path.join(full_directory, filename)
    path = os.path.dirname(full_filename)
    if not os.path.exists(path):
        os.makedirs(path)

    # logger.debug('_save_file ' + filename)
    # logger.debug('File content class name is ' + data.__class__.__name__)
    if isinstance(data, InMemoryUploadedFile):
        with default_storage.open('%s' % (full_filename), 'w') as destination:
            for chunk in data.chunks():
                destination.write(chunk)
    elif isinstance(data, File):
        # logger.debug('File name is ' + data.name)
        # if False: # full_filename.lower().endswith('.java'):
        #     # special handling for java files:
        #     # check for package and move to appropriate path
        #     short_filename = os.path.basename(filename)
        #     if filename == short_filename:
        #         # filename does not contain a package yet
        #         # => read file and search for package declaration.
        #         data.seek(0) # set file pointer to the beginning of the file
        #         # problem: File can be a binary (not text) file and
        #         # we do not know the encoding!
        #         # => convert result into string
        #         file_content = str(data.read())
        #         #import io
        #         #file_content = str(io.TextIOWrapper(io.BytesIO(data.read())))
        #         package = find_java_package_path(file_content)
        #         if len(package) > 0:
        #             logger.debug('prepend package path ' + package)
        #             full_filename = os.path.join(full_directory,  package + '/' + filename)

        #logger.debug('full_filename name is ' + full_filename)
        tmp = default_storage.save(full_filename, data)
        #logger.debug('save returned ' + tmp)
    elif isinstance(data, str): # elif data.__class__.__name__ == 'str':
        fd = open('%s' % (full_filename), 'w')
        fd.write(data)
        fd.close()
    elif isinstance(data, bytes): # data.__class__.__name__ == 'bytes':
        fd = open('%s' % (full_filename), 'wb')
        fd.write(data)
        fd.close()
    elif data.__class__.__name__ == 'PhysicalFile':
        # file already exists => move to correct location
        # logger.debug('PhysicalFile =>  ' + full_filename)
        import shutil
        shutil.move(data.path, full_filename)
        # remove folder if not empty
        shutil.rmtree(data.path, ignore_errors = True)
    else:
        raise Exception('unknown tpye: ' + data.__class__.__name__)

    # if full_filename.lower().endswith('.java'):
    #     # check if filename contains a package
    #     short_filename = os.path.basename(filename)
    #     if filename == short_filename:
    #         # no package => check if there is a package declared inside code
    #         # 1. read code
    #         with open(full_filename, 'r', encoding="latin-1") as f:
    #             file_content = f.read()
    #         # 2. seach for package
    #         package = find_java_package_path(file_content)
    #         if len(package) > 0:
    #             # 3. rename file
    #             logger.debug('prepend package path ' + package)
    #             old_full_filename = full_filename
    #             full_filename = os.path.join(full_directory, package + '/' + filename)
    #             os.replace(old_full_filename, full_filename)

    return full_filename



def _get_mimetype(txt):
    """
    :param txt:
    :return:
    """
    # Mimetype overwrite while saving -> ok to define mime as text
    # todo: use mimetypes.guess_type
    return 'text/plain'







