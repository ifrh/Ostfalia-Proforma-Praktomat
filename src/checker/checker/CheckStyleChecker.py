# -*- coding: utf-8 -*-

import shutil, os, re, subprocess
from django.conf import settings

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.html import escape
from checker.basemodels import Checker, CheckerFileField, CheckerResult, truncated_log
from checker.checker.ProFormAChecker import ProFormAChecker
from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from proforma import sandbox

import logging
logger = logging.getLogger(__name__)

use_sandbox = True

class CheckStyleChecker(ProFormAChecker):

    name = models.CharField(max_length=100, default="CheckStyle", help_text=_("Name to be displayed on the solution detail page."))
    configuration = CheckerFileField(help_text=_("XML configuration of CheckStyle. See http://checkstyle.sourceforge.net/"))

    allowedWarnings = models.IntegerField(default=0, help_text=_("How many warnings are allowed before the checker "
                                                                 "is not passed"))
    allowedErrors = models.IntegerField(default=0, help_text=_("How many errors are allowed before the checker "
                                                                 "is not passed"))
    regText = models.CharField(default=".*", max_length=5000,
                               help_text=_("Regular expression describing files to be analysed."))

    CHECKSTYLE_CHOICES = (
        (u'check-6.2', u'Checkstyle 6.2 all'),
        (u'check-7.6', u'Checkstyle 7.6 all'),
        (u'check-8.23', u'Checkstyle 8.23 all'),
        (u'check-8.29', u'Checkstyle 8.29 all'),
        (u'check-10.1', u'Checkstyle 10.1 all'),
        (u'check-10.17', u'Checkstyle 10.17 all'),
    )
    check_version = models.CharField(max_length=16, choices=CHECKSTYLE_CHOICES, default="check-8.29")

    def title(self):
        """ Returns the title for this checker category. """
        return self.name

    @staticmethod
    def description():
        """ Returns a description for this Checker. """
        return "Runs checkstyle (http://checkstyle.sourceforge.net/)."


    def run(self, env):
        self.copy_files(env)
        test_dir = env.tmpdir()

        # Save check configuration
        config_path = os.path.join(test_dir, "checks.xml")
        copy_file(self.configuration.path, config_path)

        # Run the tests
        # tests are run unsafe because checkstyle fails when network is missing
        args = ["java", "-cp", settings.CHECKSTYLE_VER[self.check_version], "-Dbasedir=.",
                "com.puppycrawl.tools.checkstyle.Main", "-c", "checks.xml"] + \
               [name for (name, content) in env.sources()]  # + [" > ", env.tmpdir() + "/output.txt"]
        if use_sandbox:
            j_sandbox = sandbox.JavaImage(self).get_container(test_dir, None)
            j_sandbox.upload_environmment()

            cmd = ' '.join(args)  # convert cmd to string
            timed_out = False
            (passed, output, timed_out) = j_sandbox.runTests(cmd, safe=False, image_suffix="cs")
            # (passed, output) = j_sandbox.exec_unsafe(cmd)

            exitcode = 0 if passed else 1
            oom_ed = False
        else:
            [output, error, exitcode, timed_out, oom_ed] = execute_arglist(args, test_dir, unsafe=True)

        # Remove Praktomat-Path-Prefixes from result:
        output = re.sub(r""+re.escape("/sandbox/")+"+", "", output, flags=re.MULTILINE)
        output = re.sub(r""+re.escape(test_dir + "/")+"+", "", output, flags=re.MULTILINE)
        warnings = str.count(output, '[WARN]')
        errors = str.count(output, '[ERROR]')

        result = self.create_result(env)
        (output, truncated) = truncated_log(output)

        # logger.debug('Exitcode is ' + str(exitcode))
        if ProFormAChecker.retrieve_subtest_results:
            # simply use plaintext
            result.set_log(output, timed_out=timed_out, truncated=False, oom_ed=oom_ed,
                           log_format=CheckerResult.TEXT_LOG)
            regexp = '\[(?<msgtype>[A-Z]+)\]\s(?<filename>\/?(.+\/)*(.+)\.([^\s:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?:\s(?<text>.+\.)\s\[(?<short>\w+)\]'
            result.set_regexp(regexp)
        else:
            # old handling (e.g. for LON-CAPA)
            log = '<pre>' + '\n\n======== Test Results ======\n\n</pre><br/><pre>' + \
                 escape(output) + '</pre>'
            # log = '<pre>' + escape(output) + '</pre>'
            if timed_out:
                log = log + '<div class="error">Timeout occured!</div>'
            if oom_ed:
                log = log + '<div class="error">Out of memory!</div>'
            result.set_log(log)

        result.set_passed(not timed_out and not oom_ed and not exitcode and
                          warnings <= self.allowedWarnings and
                          errors <= self.allowedErrors and not truncated)
        # result.set_passed(not timed_out and not oom_ed and not exitcode and (not re.match('Starting audit...\nAudit done.', output) == None))

        return result

# from checker.admin import    CheckerInline

# class CheckStyleCheckerInline(CheckerInline):
#    model = CheckStyleChecker
