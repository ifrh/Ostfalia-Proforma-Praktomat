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

from utilities.safeexec import execute_arglist
from functools import reduce

import logging
logger = logging.getLogger(__name__)

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
            regexp = '(?<filename>\/?(.+\/)*(.+)\.([^\s:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?:\s(?<msgtype>[a-z]+):\s(?<text>.+)'
            result["format"] = CheckerResult.FEEDBACK_LIST_LOG
            result["log"] = t.render({
                'filenames': filenames,
                'output': output,
                'cmdline': os.path.basename(args[0]) + ' ' +  reduce(lambda parm, ps: parm + ' ' + ps, args[1:], ''),
                'regexp': ('' if ProFormAChecker.xml_namespace == ProFormAChecker.NAMESPACES_V2_0 else regexp),
            })
        else:
            t = get_template('checker/compiler/java_builder_report.html')
            result["log"] = t.render({'filenames' : filenames, 'output' : output, 'cmdline' : os.path.basename(args[0]) + ' ' +  reduce(lambda parm, ps: parm + ' ' + ps, args[1:], '')})
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
