# -*- coding: utf-8 -*-

import re

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.html import escape
from checker.basemodels import Checker, CheckerResult, truncated_log
from checker.admin import    CheckerInline, AlwaysChangedModelForm
from checker.checker.ProFormAChecker import ProFormAChecker
from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from solutions.models import Solution
import xml.etree.ElementTree as ET

from checker.compiler.JavaBuilder import JavaBuilder
import logging
import os

logger = logging.getLogger(__name__)

RXFAIL       = re.compile(r"^(.*)(FAILURES!!!|your program crashed|cpu time limit exceeded|ABBRUCH DURCH ZEITUEBERSCHREITUNG|Could not find class|Killed|failures)(.*)$",    re.MULTILINE)

class IgnoringJavaBuilder(JavaBuilder):
    _ignore = []
    # list of jar files belonging to task
    _custom_libs = []

    def add_custom_lib(self, file):
        filename = file.path_relative_to_sandbox()
        # logger.debug('test contains JAR file: ' + filename)
        self._custom_libs.append(':' + filename)

    # add jar files belonging to task
    def libs(self):
        classpath = super().libs()
        classpath[1] += (":".join(self._custom_libs))
        return classpath

    def get_file_names(self, env):
        rxarg = re.compile(self.rxarg())
        return [name for (name, content) in env.sources() if rxarg.match(name) and (not name in self._ignore)]

    # Since this checkers instances  will not be saved(), we don't save their results, either
    def create_result(self, env):
        assert isinstance(env.solution(), Solution)
        return CheckerResult(checker=self, solution=env.solution())

class JUnitChecker(ProFormAChecker):
    """ New Checker for JUnit Unittests. """

    # Add fields to configure checker instances. You can use any of the Django fields. (See online documentation)
    # The fields created, task, public, required and always will be inherited from the abstract base class Checker
    class_name = models.CharField(
            max_length=100,
            help_text=_("The fully qualified name of the test case class (without .class)")
        )
    test_description = models.TextField(help_text = _("Description of the Testcase. To be displayed on Checker Results page when checker is  unfolded."))
    name = models.CharField(max_length=100, help_text=_("Name of the Testcase. To be displayed as title on Checker Results page"))
    ignore = models.CharField(max_length=4096, help_text=_("space-separated list of files to be ignored during compilation, i.e.: these files will not be compiled."), default="", blank=True)

    JUNIT_CHOICES = (
        (u'junit5', u'JUnit 5'),
        (u'junit4', u'JUnit 4'),
        (u'junit4.10', u'JUnit 4.10'),
        (u'junit4.12', u'JUnit 4.12'),
        (u'junit4.12-gruendel', u'JUnit 4.12 with Gruendel Addon'),
        (u'junit3', u'JUnit 3'),

    )
    junit_version = models.CharField(max_length=100, choices=JUNIT_CHOICES, default="junit3")

    def runner(self):
        return {
            'junit5': '/praktomat/lib/junit-platform-console-standalone-1.6.1.jar',
            'junit4' : 'org.junit.runner.JUnitCore',
            'junit4.10' : 'org.junit.runner.JUnitCore',
            'junit4.12' : 'org.junit.runner.JUnitCore',
            'junit4.12-gruendel' : 'org.junit.runner.JUnitCore',
            'junit3' : 'junit.textui.TestRunner'}[self.junit_version]


    def title(self):
        return "JUnit Test: " + self.name

    @staticmethod
    def description():
        return "This Checker runs a JUnit Testcases existing in the sandbox. You may want to use CreateFile Checker to create JUnit .java and possibly input data files in the sandbox before running the JavaBuilder. JUnit tests will only be able to read input data files if they are placed in the data/ subdirectory."

    def output_ok(self, output):
        return (RXFAIL.search(output) == None)

    def get_run_command_junit5(self, classpath):
        use_run_listener = ProFormAChecker.retrieve_subtest_results
        logger.debug('JUNIT 5 RunListener: ' + str(use_run_listener))
        #if settings.DETAILED_UNITTEST_OUTPUT:
        #    use_run_listener = True

        if not use_run_listener:
            # java -jar junit-platform-console-standalone-<version>.jar <Options>
            # does not work!!
            # jar = settings.JAVA_LIBS[self.junit_version]
            cmd = [settings.JVM_SECURE, "-jar", self.runner(),
               "-cp", classpath,
#               "--module-path", "/usr/share/openjfx/lib", # JFX
#               "--add-modules=javafx.base,javafx.controls,javafx.fxml,javafx.graphics,javafx.media,javafx.swing,javafx.web",
               "--include-classname", self.class_name,
               "--details=none",
               "--disable-banner", "--fail-if-no-tests",
               "--select-class", self.class_name]
        else:
            # java -cp.:/praktomat/extra/junit-platform-console-standalone-<version>.jar:/praktomat/extra/Junit5RunListener.jar
            # de.ostfalia.zell.praktomat.Junit5ProFormAListener <mainclass>
            cmd = [# "sh", "-x",
               settings.JVM_SECURE,
               "-cp", classpath + ":" + settings.JUNIT5_RUN_LISTENER_LIB,
                "--module-path", "/usr/share/openjfx/lib", # JFX
                "--add-modules=javafx.base,javafx.controls,javafx.fxml,javafx.graphics,javafx.media,javafx.swing,javafx.web",
                settings.JUNIT5_RUN_LISTENER, self.class_name]
        return cmd, use_run_listener


    def get_run_command_junit4(self, classpath):
        use_run_listener = ProFormAChecker.retrieve_subtest_results
        #if settings.DETAILED_UNITTEST_OUTPUT:
        #    use_run_listener = True

        if not use_run_listener:
            runner = self.runner()
        else:
            classpath += ":.:" + settings.JUNIT4_RUN_LISTENER_LIB
            runner = settings.JUNIT4_RUN_LISTENER
        cmd = [settings.JVM_SECURE, "-cp", classpath,
               "--module-path", "/usr/share/openjfx/lib", # JFX
               "--add-modules=javafx.base,javafx.controls,javafx.fxml,javafx.graphics,javafx.media,javafx.swing,javafx.web",
               runner, self.class_name]
        return cmd, use_run_listener

    def remove_deprecated_warning(text):
        warning1 = "WARNING: A command line option has enabled the Security Manager"
        warning2 = "WARNING: The Security Manager is deprecated and will be removed in a future release"

        if text.startswith(warning1):
            # print("found 1")
            text = text[len(warning1) + 1:]
        if text.startswith(warning2):
            # print("found 2")
            text = text[len(warning2) + 1:]
        return text

    def __is_xml_output(self, output):
        print("__is_xml_output")
        """ checks if the test output is valid xml.
        When the student calls exit in his or her code then the return code
        cannot be evaluated because the Java RunListener is not able
        to intercept the exit code and modify it to an error exit code.
        """
        root = ET.fromstring(output)
        if root.tag == "test-result":
            for score in root.findall("./result/score"):
                return True

        return False

    def run(self, env):
        # Special treatment for test cases that want to analyze the original Java student code.
        # Normally, all Java files are deleted after compilation to prevent a student from reading the test code.
        # If there is only one file in this sandbox folder (student code), then it will be restored after deletion.
        # This is only done if the student code consists of exactly one file,
        # otherwise there is a risk that the student code contains test files that would overwrite the teacher's tests.
        from pathlib import Path
        files = list(Path(env.tmpdir()).rglob("*.[jJ][aA][vV][aA]"))
        if len(files) == 1:
            # create backup file
            logger.debug(files[0])
            import shutil
            shutil.copyfile(str(files[0].absolute()), str(files[0].absolute()) + '__.bak')

        self.copy_files(env)


        # compile test
        logger.debug('JUNIT Checker build')
        java_builder = IgnoringJavaBuilder(_flags="", _libs=self.junit_version, _file_pattern=r"^.*\.[jJ][aA][vV][aA]$",
                                           _output_flags="", _main_required=False)
        # add JAR files from test task
        for file in self.files.all():
            if file.file.path.lower().endswith('.jar'):
                java_builder.add_custom_lib(file)
        java_builder._ignore = self.ignore.split(" ")

        build_result = java_builder.run(env)

        if not build_result.passed:
            logger.info('could not compile JUNIT test')
            # logger.debug("log: " + build_result.log)
            result = self.create_result(env)
            result.set_passed(False)
            result.set_log(build_result.log,
                           log_format=(CheckerResult.FEEDBACK_LIST_LOG if ProFormAChecker.retrieve_subtest_results else CheckerResult.NORMAL_LOG))
#            result.set_log('<pre>' + escape(self.test_description) + '\n\n======== Test Results ======\n\n</pre><br/>\n'+build_result.log)
            return result

        # delete all java files in the sandbox in order to avoid the student getting the test source code :-)
        [output, error, exitcode, timed_out, oom_ed] = \
            execute_arglist(['find', '.' , '-name', '*.java', '-delete'], env.tmpdir(), unsafe=True)
        if exitcode != 0:
            logger.error('exitcode for java files deletion :' + str(exitcode))
            logger.error(output)
            logger.error(error)

        if len(files) == 1:
            # restore single backup file in case of Java parser testcode
            import shutil
            shutil.copyfile(str(files[0].absolute()) + '__.bak', str(files[0].absolute()))

        # run test
        logger.debug('JUNIT Checker run')
        environ = {}

        environ['UPLOAD_ROOT'] = settings.UPLOAD_ROOT
        environ['JAVA'] = settings.JVM
        script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')
        environ['POLICY'] = os.path.join(script_dir, "junit.policy")
        print(environ)
        if not os.path.isfile(environ['POLICY']):
            raise Exception('cannot find policy file ' + os.path.isfile(environ['POLICY']))

        if self.junit_version == 'junit5':
            # JUNIT5
            [cmd, use_run_listener] = self.get_run_command_junit5(java_builder.libs()[1])
        else:
            # JUNIT4
            [cmd, use_run_listener] = self.get_run_command_junit4(java_builder.libs()[1])

        # use Java security manager instead of restrict application        
        [output, error, exitcode, timed_out, oom_ed] = \
            execute_arglist(cmd, env.tmpdir(), environment_variables=environ, timeout=settings.TEST_TIMEOUT,
                            fileseeklimit=settings.TEST_MAXFILESIZE, extradirs=[script_dir], unsafe=True)

        # Remove deprecated warning for Java 17 and security manager
        output = JUnitChecker.remove_deprecated_warning(output)
        logger.debug('JUNIT output:' + str(output))
        logger.debug('JUNIT error:' + str(error))
        logger.debug('JUNIT exitcode:' + str(exitcode))

        result = self.create_result(env)
        truncated = False
        # show normal console output in case of:
        # - timeout (created by Checker)
        # - not using RunListener
        # - exitcode <> 0 with RunListener (means internal error)
        if timed_out or oom_ed:
            # ERROR: Execution timed out
            logger.error('Execution timeout')
            if use_run_listener:
                # clear log for timeout with Run Listener
                # because truncating log will result in invalid XML.
                output = ''
                truncated = False
            output = '\Execution timed out... (Check for infinite loop in your code)\r\n' + output
            (output, truncated) = truncated_log(output)
            # Do not set timout flag in order to handle timeout only as failed testcase.
            # Student shall be motivated to look for error in his or her code and not in testcode.
            result.set_log(output, timed_out=False, truncated=truncated, oom_ed=oom_ed, log_format=CheckerResult.TEXT_LOG)
            result.set_passed(False)
            return result

        #import chardet
        #encoding = chardet.detect(output)
        #logger.debug('JUNIT output encoding:' + encoding['encoding'])

        if use_run_listener:
            # RUN LISTENER
            if exitcode != 0 and self.__is_xml_output(output):
                exitcode = 0

            if exitcode == 0:
                # normal detailed XML results
                # todo: Unterscheiden zwischen Textlistener (altes Log-Format) und Proforma-Listener (neues Format)
                result.set_log(output, timed_out=timed_out, truncated=False, oom_ed=oom_ed, log_format=CheckerResult.PROFORMA_SUBTESTS)
            else:
                result.set_internal_error(True)
                # no XML output => truncate
                (output, truncated) = truncated_log(output)
                result.set_log("RunListener Error: " + output, timed_out=timed_out, truncated=truncated, oom_ed=oom_ed,
                               log_format=CheckerResult.TEXT_LOG)
        else:
            # show standard log output
            (output, truncated) = truncated_log(output)
            output = '<pre>' + escape(self.test_description) + '\n\n======== Test Results ======\n\n</pre><br/><pre>' + \
                 escape(output) + '</pre>'
            result.set_log(output, timed_out=timed_out or oom_ed, truncated=truncated, oom_ed=oom_ed)

        result.set_passed(not exitcode and self.output_ok(output) and not truncated)
        return result

#class JUnitCheckerForm(AlwaysChangedModelForm):
#    def __init__(self, **args):
#        """ override default values for the model fields """
#        super(JUnitCheckerForm, self).__init__(**args)
#        self.fields["_flags"].initial = ""
#        self.fields["_output_flags"].initial = ""
#        self.fields["_libs"].initial = "junit3"
#        self.fields["_file_pattern"].initial = r"^.*\.[jJ][aA][vV][aA]$"

class JavaBuilderInline(CheckerInline):
    """ This Class defines how the the the checker is represented as inline in the task admin page. """
    model = JUnitChecker
#    form = JUnitCheckerForm

# A more advanced example: By overwriting the form of the checkerinline the initial values of the inherited atributes can be overritten.
# An other example would be to validate the inputfields in the form. (See Django documentation)
#class ExampleForm(AlwaysChangedModelForm):
    #def __init__(self, **args):
        #""" override public and required """
        #super(ExampleForm, self).__init__(**args)
        #self.fields["public"].initial = False
        #self.fields["required"].initial = False

#class ExampleCheckerInline(CheckerInline):
    #model = ExampleChecker
    #form = ExampleForm
