# -*- coding: utf-8 -*-

"""
A Java bytecode compiler for construction.
"""

import os, re
import string
from checker.compiler.Builder import Builder
from django.conf import settings
from django.template.loader import get_template
from checker.basemodels import Checker, CheckerResult
from checker.checker.ProFormAChecker import ProFormAChecker
from proforma import sandbox

from utilities.safeexec import execute_arglist
from functools import reduce
from django.template.defaultfilters import escape

import logging
logger = logging.getLogger(__name__)

use_docker_sandbox = True

class ClassFileGeneratingBuilder(Builder):
    """ A base class for Builders that generate .class files """

    class Meta(Checker.Meta):
        abstract = True

    def main_module(self, env):
        """ find the first class file containing a main method """
        main_method = "public static void main(java.lang.String[])"
        main_method_varargs = "public static void main(java.lang.String...)"
        class_name  = re.compile(r"^(public )?(abstract )?(final )?class ([^ ]*)( extends .*)?( implements .*)? \{$", re.MULTILINE)
        class_files = []
        for dirpath, dirs, files in os.walk(env.tmpdir()):
            for filename in files:
                if filename.endswith(".class"):
                    class_files.append(filename)
                    [classinfo, _, _, _, _]  = execute_arglist([settings.JAVAP, os.path.join(dirpath, filename)], env.tmpdir(), self.environment(), unsafe=True)
                    if classinfo.find(main_method) >= 0 or classinfo.find(main_method_varargs) >= 0:
                        main_class_name = class_name.search(classinfo, re.MULTILINE).group(4)
                        return main_class_name

        raise self.NotFoundError("A class containing the main method ('public static void main(String[] args)') could not be found in the files %s" % ", ".join(class_files))

class JavaBuilder(ClassFileGeneratingBuilder):
    """     A Java bytecode compiler for construction. """

    # Initialization sets own attributes to default values.
    _compiler    = settings.JAVA_BINARY_SECURE
    _language    = "Java"
    _env            = {}
    _env['JAVAC'] = settings.JAVA_BINARY
    _env['JAVAP'] = settings.JAVAP

    def libs(self):
        def toPath(lib):
            if lib=="junit3":
                 return settings.JUNIT38_JAR
            return lib

        required_libs = super(JavaBuilder, self).libs()

        return ["-cp", ".:"+(":".join([ settings.JAVA_LIBS[lib] for lib in required_libs if lib in settings.JAVA_LIBS ]))]

    def flags(self, env):
        """ Accept unicode characters. """
        return (self._flags.split(" ") if self._flags else []) + \
               ["-encoding", "utf-8"] + \
               ["--module-path", "/usr/share/openjfx/lib"] + \
               ["--add-modules=javafx.base,javafx.controls,javafx.fxml,javafx.graphics,javafx.media,javafx.swing,javafx.web"]


    # override
    def enhance_output(self, env, output):
        """ Add more info to build output OUTPUT.  To be overloaded in subclasses. """
        if ProFormAChecker.retrieve_subtest_results:
            # do not enhance in case of Proforma format
            return output
        return Builder.enhance_output(self, env, output)

    def build_log(self, output, args, filenames):
        result = dict()
        if ProFormAChecker.retrieve_subtest_results:
            t = get_template('checker/compiler/java_builder_report.xml')
            regexp = '(?<filename>\/?(\w+\/)*(\w+)\.([^:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?: (?<msgtype>[a-z]+): (?<text>.+)(?<code>\s+.+)?(?<position>\s+\^)?(\s+symbol:\s*(?<symbol>\s+.+))?'
#            regexp = '(?<filename>\/?(.+\/)*(.+)\.([^\s:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?:\s(?<msgtype>[a-z]+):\s(?<text>.+)'
            result["format"] = CheckerResult.FEEDBACK_LIST_LOG
            # in order to improve testability sort all filenames alphabetically
            sorted_filenames = sorted(filenames)
            result["log"] = t.render({
                'filenames': sorted_filenames,
                'output': output,
                'cmdline': os.path.basename(args[0]) + ' ' +  reduce(lambda parm, ps: parm + ' ' + ps, args[1:], ''),
                'regexp': ('' if ProFormAChecker.xml_namespace == ProFormAChecker.NAMESPACES_V2_0 else regexp),
            })
        else:
            t = get_template('checker/compiler/java_builder_report.html')
            result["log"] = t.render({'filenames' : filenames, 'output' : output, 'cmdline' : os.path.basename(args[0]) + ' ' +  reduce(lambda parm, ps: parm + ' ' + ps, args[1:], '')})
        return result

    def run(self, env):
        if not use_docker_sandbox:
            return super().run(env)

        """ Build it. """
        logger.debug("---- compile test start ----")
        test_dir = env.tmpdir()

        filenames = [name for name in self.get_file_names(env)]
        args = ['javac'] + self.output_flags(env) + self.flags(env) + filenames + self.libs()
        cmd = ' '.join(args)  # convert cmd to string
        # script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')

####

        #        [output, _, _, _, _]  = execute_arglist(args, env.tmpdir(), self.environment(), extradirs=[script_dir], unsafe=True)

        ####
        j_sandbox = sandbox.JavaImage(self).get_container(test_dir, None)
        j_sandbox.upload_environmment()
        # compile
        (passed, output) = j_sandbox.compile_tests(cmd)
        logger.debug("compilation passed is " + str(passed))
        logger.debug(output)
        if not passed:
            return self.handle_compile_error(env, output, "", False, False)
        exitcode = 0
#####
        result = self.create_result(env)

        output = escape(output)
        output = self.enhance_output(env, output)

        # We mustn't have any warnings.
        passed = passed and not self.has_warnings(output)
        log = self.build_log(output, args, set(filenames).intersection(
            [solutionfile.path() for solutionfile in env.solution().solutionfile_set.all()]))
        if not "format" in log:
            log["format"] = CheckerResult.NORMAL_LOG

        result.set_passed(passed)
        result.set_log(log["log"], log_format=log["format"])
        logger.debug(output)
        logger.debug("---- compile test end ----")

        return result



from checker.admin import CheckerInline, AlwaysChangedModelForm

class CheckerForm(AlwaysChangedModelForm):
    def __init__(self, **args):
        """ override default values for the model fields """
        super(CheckerForm, self).__init__(**args)
        self.fields["_flags"].initial = ""
        self.fields["_output_flags"].initial = ""
        #self.fields["_libs"].initial = ""
        self.fields["_file_pattern"].initial = r"^.*\.[jJ][aA][vV][aA]$"

class JavaBuilderInline(CheckerInline):
    model = JavaBuilder
    form = CheckerForm
