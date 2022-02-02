# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import Checker
from checker.checker.CreateFileChecker import CreateFileChecker
from checker.basemodels import CheckerResult, truncated_log
from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from django.template.loader import get_template
from functools import reduce
from django.utils.html import escape



import os
import logging
logger = logging.getLogger(__name__)

class ProFormAChecker(Checker):
    """ Checker referencing Files (abstract class) """

    # Add fields to configure checker instances. You can use any of the Django fields. (See online documentation)

    proforma_id = models.CharField(default="None", max_length=255, help_text = _('Is needed for ProFormA'))

    files = models.ManyToManyField(CreateFileChecker, help_text=_("Files needed to run the test"))

    # class variable indicating if the tests shall get as much information about
    # subtests as possible (e.g. use RunListener for JUnit)
    retrieve_subtest_results = True

    # class variable for storing the XML response namespace
    NAMESPACES_V2_0 = 'urn:proforma:v2.0'
    NAMESPACES_V2_1 = 'urn:proforma:v2.1'
    xml_namespace = NAMESPACES_V2_1

    def get_file_names(self, env):
        # rxarg = re.compile(self.rxarg())
        return [name for (name, content) in env.sources()]


    def copy_files(self, env):
        logger.debug('copy test files')
        for file in self.files.all():
            logger.debug('file: ' + file.file.path)
            file.run(env)


    # remove all files with a given extension
    def remove_source_files(self, env, extensions):
        logger.debug('remove source files')
        # remove all files with extension c
        files_in_directory = os.listdir(env.tmpdir())
        for root, dirs, files in os.walk(env.tmpdir()):
            for file in files:
                if file.lower().endswith(extensions):
                    # logger.debug('remove ' + file)
                    cmd = ['rm', file]
                    [output, error, exitcode, timed_out, oom_ed] = \
                        execute_arglist(cmd, env.tmpdir())
                    # os.remove fails because of missing permissions
                    #try:
                    #    os.remove(os.path.join(root, file))
                    #except:
                    #    logger.error("Error while deleting file : ", file)
                    
                    
    def build_compilation_error_log(self, output, args, filenames):
        result = dict()
        if ProFormAChecker.retrieve_subtest_results:
            t = get_template('checker/compiler/proforma_builder_report.xml')
            regexp = '(?<filename>\/?(\w+\/)*(\w+)\.([^:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?: (?<msgtype>[a-z]+): (?<text>.+)(?<code>\s+.+)?(?<position>\s+\^)?(\s+symbol:\s*(?<symbol>\s+.+))?'
#            regexp = '(?<filename>\/?(.+\/)*(.+)\.([^\s:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?:\s(?<msgtype>[a-z]+):\s(?<text>.+)'
            result["format"] = CheckerResult.FEEDBACK_LIST_LOG
            result["log"] = t.render({
                'filenames': filenames,
                'output': output,
                'cmdline': 'no commandline', #os.path.basename(args[0]) + ' ' +  reduce(lambda parm, ps: parm + ' ' + ps, args[1:], ''),
                'regexp': ('' if ProFormAChecker.xml_namespace == ProFormAChecker.NAMESPACES_V2_0 else regexp),
            })
        else:
            t = get_template('checker/compiler/proforma_builder_report.html')
            result["log"] = t.render({'filenames' : filenames, 'output' : output, 
                'cmdline' : os.path.basename(args[0]) + ' ' +  reduce(lambda parm, ps: parm + ' ' + ps, args[1:], '')})
        return result
                    
    def remove_sandbox_paths(self, output, env):
        return output.replace(env.tmpdir() + "/", "")

    # default handling of exit code error
    def handle_command_error(self, env, output, error, timed_out, oom_ed):
        logger.error("output: " + output)
        output = self.remove_sandbox_paths(output, env)
        result = self.create_result(env)
        result.set_passed(False)
        if error != None and len(error) > 0:
            logger.error("error: " + error)
            output = output + error
        (output, truncated) = truncated_log(output)
        output = escape(output)
        
        filenames = [name for name in self.get_file_names(env)]
        submissionfiles = set(filenames).intersection([solutionfile.path() for solutionfile in env.solution().solutionfile_set.all()])
        log = self.build_compilation_error_log(output, '', submissionfiles)
        
        result.set_log(log["log"], timed_out=timed_out or oom_ed, truncated=truncated, oom_ed=oom_ed, log_format=log["format"])
        # result.set_log(log["log"], log_format=log["format"])

        return result                    
        
    def prepare_run(self, env):
        self.copy_files(env)
        # check if there is only one file with extension zip
        if self.files.count() == 1:
            for file in self.files.all():
                if file.filename.lower().endswith('.zip'):
                    # unpack zip file
                    unpack_zipfile_to(env.tmpdir() + '/' + file.filename, env.tmpdir())

    def compile_make(self, env):
        # compile CMakeLists.txt
        if os.path.exists(env.tmpdir() + '/CMakeLists.txt'):
            logger.debug('cmakefile found, execute cmake')
            [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['cmake', '.'], env.tmpdir())
            if exitcode != 0:
                return self.handle_command_error(env, output, error, timed_out, oom_ed)

        # run make
        logger.debug('make')
        [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['make'], env.tmpdir())
        if exitcode != 0:
            # suppress as much information as needed
            # call make twice in order to get only errors in student code
            [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['make'], env.tmpdir())
            if error != None:
                # delete output when error text exists because output contains a lot of irrelevant information
                # for student
                # logger.error(error)
                output = error
                error = ''
            return self.handle_command_error(env, output, error, timed_out, oom_ed)
            
        return True

    
    