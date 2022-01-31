# -*- coding: utf-8 -*-

import re

from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import CheckerResult, truncated_log
from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from checker.checker.ProFormAChecker import ProFormAChecker


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

        build_result = self.compile_make(env)
        if build_result != True:
            return build_result

        extensions = ('.c', '.h')
        self.remove_source_files(env, extensions)

        # run program
        logger.debug('run ' + self.class_name)
        cmd = [self.class_name]
        [output, error, exitcode, timed_out, oom_ed] = \
            execute_arglist(cmd, env.tmpdir(), timeout=settings.TEST_TIMEOUT, fileseeklimit=settings.TEST_MAXFILESIZE)
        logger.debug(output)
        logger.debug("exitcode: " + str(exitcode))

        # get result
        result = self.create_result(env)
        if error != None and len(error) > 0:
            logger.debug(error)
            output = output + error
        (output, truncated) = truncated_log(output)
        result.set_log(output, timed_out=timed_out or oom_ed, truncated=truncated, oom_ed=oom_ed,
                       log_format=CheckerResult.TEXT_LOG)
        result.set_passed(not exitcode and not timed_out and not oom_ed and self.output_ok(output) and not truncated)
        return result

