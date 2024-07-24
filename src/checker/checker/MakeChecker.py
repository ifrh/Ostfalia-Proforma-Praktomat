# -*- coding: utf-8 -*-

import re

from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import CheckerResult, truncated_log
#from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from checker.checker.ProFormAChecker import ProFormAChecker
from proforma import sandbox


import logging
logger = logging.getLogger(__name__)

RXFAIL       = re.compile(r"^(.*)(FAILURES!!!|your program crashed|cpu time limit exceeded|ABBRUCH DURCH ZEITUEBERSCHREITUNG|Could not find class|Killed|failures)(.*)$",    re.MULTILINE)

class MakeChecker(ProFormAChecker):
    """ New Checker for Unittests using a makefile for compilation. """

    # Add fields to configure checker instances. You can use any of the Django fields. (See online documentation)
    # The fields created, task, public, required and always will be inherited from the abstract base class Checker
    class_name = models.CharField(
            max_length=100,
            help_text=_("The fully qualified name of the test case class (without .class)")
        )
    test_description = models.TextField(help_text = _("Description of the Testcase. To be displayed on Checker Results page when checker is  unfolded."))
    name = models.CharField(max_length=100, help_text=_("Name of the Testcase. To be displayed as title on Checker Results page"))
    # ignore = models.CharField(max_length=4096, help_text=_("space-separated list of files to be ignored during compilation, i.e.: these files will not be compiled."), default="", blank=True)


    def title(self):
        return "CUnit Test: " + self.name

    @staticmethod
    def description():
        return "This Checker runs a Testcases existing in the sandbox compiled with a makefile."

    def output_ok(self, output):
        return (RXFAIL.search(output) == None)


    def run(self, env):
        # copy files and unzip zip file if submission consists of just a zip file.
        self.prepare_run(env)
        test_dir = env.tmpdir()

        # cmd = [self.class_name]
        gt_sandbox = sandbox.CppImage(self).get_container(test_dir, self.class_name)
        gt_sandbox.upload_environmment()
        # run test
        (passed, output) = gt_sandbox.compile_tests()
        if not passed:
            return self.handle_compile_error(env, output, "", False, False)
        (passed, output, timeout) = gt_sandbox.runTests(image_suffix="make")
        logger.debug("passed " + str(passed))
        logger.debug("output " + output)
        result = self.create_result(env)

        # if passed:
        #    gt_sandbox.get_result_file()

        # # compile
        # build_result = self.compile_make(env)
        # if build_result != True:
        #     return build_result
        #
        # # remove source code files
        # extensions = ('.c', '.h', '.a', '.o', 'CMakeCache.txt', 'Makefile', 'makefile', 'CMakeLists.txt',
        #               'cmake_install.cmake')
        # self.remove_source_files(env, extensions)
        #
        # # copy shared objects
        # self.copy_shared_objects(env)
        #
        # # run test
        # logger.debug('run ' + self.class_name)
        # cmd = [self.class_name]
        # #[output, error, exitcode, timed_out, oom_ed] = \
        # #    execute_arglist(cmd, env.tmpdir(), timeout=settings.TEST_TIMEOUT, fileseeklimit=settings.TEST_MAXFILESIZE)
        # #logger.debug(output)
        # #logger.debug("exitcode: " + str(exitcode))
        #
        # # get result
        # (result, output) = self.run_command(cmd, env)
        #if not passed:
        #     # error
        #     return result
					
        (output, truncated) = truncated_log(output)
        result.set_log(output, timed_out=timeout, truncated=truncated, oom_ed=False,
                       log_format=CheckerResult.TEXT_LOG)
        result.set_passed(passed and not truncated)
        return result

