# -*- coding: utf-8 -*-

import re
from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import CheckerFileField, CheckerResult, truncated_log
from utilities.file_operations import *
from django.utils.html import escape
from checker.checker.ProFormAChecker import ProFormAChecker
from proforma import sandbox

import os

import logging
logger = logging.getLogger(__name__)


RXFAIL = re.compile(
    r"^(.*)(FAILURES!!!|your program crashed|cpu time limit exceeded|"
    r"ABBRUCH DURCH ZEITUEBERSCHREITUNG|Could not find class|Killed|Fehler:|"
    r"failures|Die Einreichung ist nicht richtig)(.*)$",
    re.MULTILINE)

RXPASS = re.compile(r"(Test passed.)$",
                    re.MULTILINE)
RXSECURE = re.compile(r"(import(?! math\s*$)(?! numpy\s*$)|open\s*\(|file\s*\(|execfile|exec|compile|reload|__|eval)",
                      re.MULTILINE)
RXCODING = re.compile(r"coding[=:]\s*([-\w.]+)")

RXSHEBANG = re.compile(r"(#!)+.*", re.MULTILINE)



class PythonDoctestSandbox(sandbox.DockerSandbox):
    def __init__(self, client, studentenv, command):
        super().__init__(client, studentenv,
                         "python3 -m compileall /sandbox -q", # compile command
                         command, # run command
                         None) # download path


class PythonDoctestImage(sandbox.PythonImage):
    """ derive from PythonImage in order to support requirements """
    def __init__(self, praktomat_test):
        super().__init__(praktomat_test)

    def get_container(self, studentenv, command):
        self.create_image()  # function is generator, so this must be handled in order to be executed
        sandbox = PythonDoctestSandbox(self._client, studentenv, command)
        sandbox.create(self._get_image_fullname(self._get_image_tag()))
        return sandbox



class PythonChecker(ProFormAChecker):
    name = models.CharField(max_length=100, default="Externen Tutor ausführen",
                            help_text=_("Name to be displayed on the solution detail page."))
    doctest = CheckerFileField(
        help_text=_("The doctest script."))
    remove = models.CharField(max_length=5000, blank=True,
                              help_text=_("Regular expression describing passages to be removed from the output."))
    returns_html = models.BooleanField(default=False, help_text=_(
        "If the script doesn't return HTML it will be enclosed in &lt; pre &gt; tags."))

    def title(self):
        """ Returns the title for this checker category. """
        return self.name

    @staticmethod
    def description():
        """ Returns a description for this Checker. """
        return u"Diese Prüfung wird bestanden, wenn das externe Programm keinen Fehlercode liefert."

    def output_ok(self, output):
        return RXFAIL.search(output) is None

    def output_ok_positiv(self, output):
        print(RXPASS.search(output))

        x = re.search("Test passed.", output)
        print(x)

        if RXPASS.search(output):
            return True
        else:
            return False

    def checkSubmission(self, submission):
        if RXSECURE.search(submission) or RXSHEBANG.search(submission):
        #  if RXSECURE.search(submission) or RXCODING.search(submission) or RXSHEBANG.search(submission):
                return True
        else:
            return False

    def run(self, env):
        """ Runs tests in a special environment. Here's the actual work.
        This runs the check in the environment ENV, returning a CheckerResult. """

        test_dir = env.tmpdir()
        # Setup
        # copy files and unzip zip file if submission consists of just a zip file.
        self.prepare_run(env)

        # replace = [(u'PROGRAM', env.program())] if env.program() else []
        # copy test files (why are they not copied in prepare_run?)
        copy_file(self.doctest.path, os.path.join(test_dir,
                        os.path.basename(self.doctest.path)))
        # script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')

        for (name, content) in env.sources():
            if self.checkSubmission(content):
                result = CheckerResult(checker=self)
                result.set_passed(False)
                result.set_log("Bitte überarbeiten Sie Ihren Programmcode: "
                               "Betriebssystem kritische Befehle sind verboten")
                return result

        run_cmd = "python3 " + os.path.basename(self.doctest.name) + " -v"
        logger.debug(run_cmd)

        p_sandbox = PythonDoctestImage(self).get_container(test_dir, run_cmd)
        p_sandbox.upload_environmment()

        # precompile
        (passed, output) = p_sandbox.compile_tests()
        logger.debug("compilation passed is "+ str(passed))
        logger.debug(output)
        if not passed:
            return self.handle_compile_error(env, output, "", False, False)

        # run test
        (passed, output, timeout) = p_sandbox.runTests(image_suffix="python")
        result = self.create_result(env)
        (output, truncated) = truncated_log(output)

        if self.remove:
            output = re.sub(self.remove, "", output)

        output = output.strip() # remove whitespace characters from output - needed for regular expression

        # Remove Praktomat-Path-Prefixes from result:
        #output = re.sub(r"^"+re.escape(test_dir)+"/+", "", output, flags=re.MULTILINE)
        output = re.sub(r"^"+re.escape("/sandbox")+"/+", "", output, flags=re.MULTILINE)
        if ProFormAChecker.retrieve_subtest_results:
            # plain text output
            result.set_log(output, timed_out=timeout, truncated=truncated, log_format=CheckerResult.TEXT_LOG)
        else:
            if not self.returns_html:
                output = '<pre>' + output + '</pre>'
            output = '<pre>' + '\n\n======== Test Results ======\n\n</pre><br/><pre>' + \
                 escape(output) + '</pre>'
            result.set_log(output, timed_out=timeout, truncated=truncated)

        logger.debug(output)
        result.set_passed(passed and not timeout and self.output_ok_positiv(output) and not truncated)

        return result

