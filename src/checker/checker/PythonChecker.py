# -*- coding: utf-8 -*-

import re
from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.models import Checker, CheckerFileField, CheckerResult, execute_arglist, truncated_log
from utilities.file_operations import *
from django.utils.html import escape

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

class PythonChecker(Checker):
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

    def removeSystemPath(self, output, env):
        output = re.sub(env.tmpdir(), "", output, flags=re.MULTILINE)
        output = re.sub("/usr/lib/python2.7/", "", output, flags=re.MULTILINE)
        return output

    def run(self, env):
        """ Runs tests in a special environment. Here's the actual work.
        This runs the check in the environment ENV, returning a CheckerResult. """

        # Setup
        test_dir = env.tmpdir()
        replace = [(u'PROGRAM', env.program())] if env.program() else []
        task_folder(self.doctest.path, test_dir, replace=replace)
        script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')

        # Run the tests -- execute dumped shell script 'script.sh'
        cmd = ["python", os.path.basename(self.doctest.name), "-v"]
        environ = dict()
        environ['USER'] = env.user().get_full_name()
        environ['HOME'] = test_dir

        for (name, content) in env.sources():
            if self.checkSubmission(content):
                result = CheckerResult(checker=self)
                result.set_passed(False)
                result.set_log("Bitte überarbeiten Sie Ihren Programmcode: "
                               "Betriebssystem kritische Befehle sind verboten")
                return result

        # (output, error, exitcode) = execute(args, working_directory=test_dir, environment_variables=environ)

        [output, error, exitcode, timed_out] = execute_arglist(cmd, env.tmpdir(),
                                                               environment_variables=environ,
                                                               use_default_user_configuration=True,
                                                               timeout=settings.TEST_TIMEOUT,
                                                               fileseeklimit=settings.TEST_MAXFILESIZE,
                                                               extradirs=[script_dir])

        result = CheckerResult(checker=self)
        (output, truncated) = truncated_log(output)

        if self.remove:
            output = re.sub(self.remove, "", output)
        if not self.returns_html:
            output = '<pre>' + output + '</pre>'
        # decode utf-8 really?
        result.set_log(output.decode("utf-8", "ignore"))

        # Remove Praktomat-Path-Prefixes from result:
        output = re.sub(r"^"+re.escape(env.tmpdir())+"/+", "", output, flags=re.MULTILINE)

        output = '<pre>' + '\n\n======== Test Results ======\n\n</pre><br/><pre>' + \
                 escape(output) + '</pre>'
        result.set_log(output, timed_out=timed_out, truncated=truncated)
        result.set_passed(not exitcode and not timed_out and self.output_ok_positiv(output) and not truncated)

        return result


from checker.admin import CheckerInline


class PythonCheckerInline(CheckerInline):
    model = PythonChecker