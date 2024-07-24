# -*- coding: utf-8 -*-

import re

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.html import escape
from checker.basemodels import Checker, CheckerResult, truncated_log
# from checker.admin import    CheckerInline, AlwaysChangedModelForm
from checker.checker.ProFormAChecker import ProFormAChecker
# from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from solutions.models import Solution
import xml.etree.ElementTree as ET
from proforma import sandbox

from checker.compiler.JavaBuilder import JavaBuilder
import logging
import os

logger = logging.getLogger(__name__)

RXFAIL       = re.compile(r"^(.*)(FAILURES!!!|your program crashed|cpu time limit exceeded|ABBRUCH DURCH ZEITUEBERSCHREITUNG|Could not find class|Killed|failures)(.*)$",    re.MULTILINE)


use_sandbox = True

class IgnoringJavaBuilder(JavaBuilder):
    _ignore = []
    # list of jar files belonging to task
    _custom_libs = []
    JAVA_BIN = 'java' if use_sandbox else settings.JVM_SECURE

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

    def get_run_command(self, env):
        """ Build it. """
        # Try to find out the main modules name with only the source files present
        if self._main_required:
            try:
                env.set_program(self.main_module(env))
            except self.NotFoundError:
                pass

        filenames = [name for name in self.get_file_names(env)]
        args = ["javac"]
#        args = ["javac"] + self.output_flags(env) + self.flags(env) + filenames + self.libs()
        if use_sandbox:
            args += ['-d'] + ['.']
        args += self.output_flags(env) + self.flags(env) + filenames + self.libs()


        return ' '.join(args)




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
            cmd = [IgnoringJavaBuilder.JAVA_BIN, "-jar", self.runner(),
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
               IgnoringJavaBuilder.JAVA_BIN,
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
        cmd = [IgnoringJavaBuilder.JAVA_BIN, "-cp", classpath,
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

    def _is_xml_output(self, output):
        print("__is_xml_output")
        """ checks if the test output is valid xml.
        """
        try:
            root = ET.fromstring(output)
            if root.tag == "test-result":
                for score in root.findall("./result/score"):
                    return True
        except:
            pass

        return False

    def run(self, env):
        # Special treatment for test cases that want to analyze the original Java student code.
        # Normally, all Java files are deleted after compilation to prevent a student from reading the test code.
        # If there is only one file in this sandbox folder (student code), then it will be restored after deletion.
        # This is only done if the student code consists of exactly one file,
        # otherwise there is a risk that the student code contains test files that would overwrite the teacher's tests.
        from pathlib import Path
        logger.debug("---- junit test start ----")
        test_dir = env.tmpdir()
        files = list(Path(test_dir).rglob("*.[jJ][aA][vV][aA]"))
        restore_backup = False
        restore_filename = None
        if len(files) == 1:
            restore_backup = True
            # create backup file
            restore_filename = str(files[0].absolute())[len(test_dir)+1:]
            import shutil
            shutil.copyfile(str(files[0].absolute()), str(files[0].absolute()) + '__.bak')

        # os.system('ls -al ' + test_dir)
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

################
        if use_sandbox:
            # use sandbox instead of Java security manager
            j_sandbox = sandbox.JavaImage(self).get_container(test_dir, None)
            j_sandbox.upload_environmment()
            # compile
            # j_sandbox.exec('ls -al')
            (passed, output) = j_sandbox.compile_tests(java_builder.get_run_command(env))
            logger.debug("compilation passed is " + str(passed))
            logger.debug(output)
            if not passed:
                return self.handle_compile_error(env, output, "", False, False)
            exitcode = 0
            (passed1, out) = j_sandbox.exec('find . -name *.java -delete')
            if not passed1:
                logger.error('java files deletion failed')
                logger.error(out)
            if restore_backup:
                # restore single backup file in case of Java parser testcode
                (passed1, out) = j_sandbox.exec('mv ' + restore_filename + '__.bak ' + restore_filename)

        # else:
        #     build_result = java_builder.run(env)
        #
        #     if not build_result.passed:
        #         logger.info('could not compile JUNIT test')
        #         # logger.debug("log: " + build_result.log)
        #         result = self.create_result(env)
        #         result.set_passed(False)
        #         result.set_log(build_result.log,
        #                        log_format=(
        #                            CheckerResult.FEEDBACK_LIST_LOG if ProFormAChecker.retrieve_subtest_results else CheckerResult.NORMAL_LOG))
        #         #            result.set_log('<pre>' + escape(self.test_description) + '\n\n======== Test Results ======\n\n</pre><br/>\n'+build_result.log)
        #         return result
        #     # delete all java files in the sandbox in order to avoid the student getting the test source code :-)
        #     [output, error, exitcode, timed_out, oom_ed] = \
        #         execute_arglist(['find', '.' , '-name', '*.java', '-delete'], test_dir, unsafe=True)
        #     if exitcode != 0:
        #         logger.error('exitcode for java files deletion :' + str(exitcode))
        #         logger.error(output)
        #         logger.error(error)
        #
        #     if len(files) == 1:
        #         # restore single backup file in case of Java parser testcode
        #         import shutil
        #         shutil.move(str(files[0].absolute()) + '__.bak', str(files[0].absolute()))
        #
################

        # run test
        logger.debug('JUNIT Checker run')
        if self.junit_version == 'junit5':
            # JUNIT5
            [cmd, use_run_listener] = self.get_run_command_junit5(java_builder.libs()[1])
        else:
            # JUNIT4
            [cmd, use_run_listener] = self.get_run_command_junit4(java_builder.libs()[1])

################

        if use_sandbox:
            # run
            cmd = ' '.join(cmd)  # convert cmd to string
            # logger.debug(cmd)
            # j_sandbox.exec('ls -al')

            (passed, output, timed_out) = j_sandbox.runTests(command=cmd, image_suffix="junit")
#            (passed, output, timed_out) = j_sandbox.runTests("tail -f /dev/null")
            # logger.debug(output)
            exitcode = 0 if passed else 1
            oom_ed = False

        # else:
        #     environ = {}
        #
        #     environ['UPLOAD_ROOT'] = settings.UPLOAD_ROOT
        #     environ['JAVA'] = settings.JVM
        #     script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')
        #     environ['POLICY'] = os.path.join(script_dir, "junit.policy")
        #     print(environ)
        #     if not os.path.isfile(environ['POLICY']):
        #         raise Exception('cannot find policy file ' + os.path.isfile(environ['POLICY']))
        #     [output, error, exitcode, timed_out, oom_ed] = \
        #         execute_arglist(cmd, test_dir, environment_variables=environ, timeout=settings.TEST_TIMEOUT,
        #                         fileseeklimit=settings.TEST_MAXFILESIZE, extradirs=[script_dir], unsafe=True)
        #     # Remove deprecated warning for Java 17 and security manager
        #     output = JUnitChecker.remove_deprecated_warning(output)
        #     logger.debug('JUNIT output:' + str(output))
        #     logger.debug('JUNIT error:' + str(error))
        #     logger.debug('JUNIT exitcode:' + str(exitcode))


################

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
            # When the student calls exit in his or her code then the return code
            # cannot be evaluated because the Java RunListener is not able
            # to intercept the exit code and modify it to an error exit code.
            # Therefore in case of an exit code <> 0 (expecting no XML)
            # it is checked whether there is valid XML output.
            if exitcode != 0 and self._is_xml_output(output):
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
            logger.debug("use standard output")
            (output, truncated) = truncated_log(output)
            output = '<pre>' + escape(self.test_description) + '\n\n======== Test Results ======\n\n</pre><br/><pre>' + \
                 escape(output) + '</pre>'
            result.set_log(output, timed_out=timed_out or oom_ed, truncated=truncated, oom_ed=oom_ed)

        result.set_passed(not exitcode and self.output_ok(output) and not truncated)
        # logger.debug("---- junit test end ----")

        return result




