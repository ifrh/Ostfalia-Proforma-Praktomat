# -*- coding: utf-8 -*-
import os.path
import shutil
import sys
import time

from django.conf import settings
from django.db import models
from tasks.models import Task
from solutions.models import Solution
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db.models.signals import post_delete
from django.dispatch.dispatcher import receiver
from utilities import encoding, file_operations
from utilities.deleting_file_field import DeletingFileField
from utilities.safeexec import execute_command

from functools import partial
from multiprocessing import Pool

from django.db import transaction
from django import db
from django.db import connection

import logging
logger = logging.getLogger(__name__)

def get_checkerfile_storage_path(instance, filename):
    """ Use this function as upload_to parameter for filefields. """
    return 'CheckerFiles/Task_%s/%s/%s' % (instance.task.pk, instance.__class__.__name__, filename)


class CheckerFileField(DeletingFileField):
    """ Custom filefield with greater path length and default upload location. Use this in all checker subclasses!"""

    def __init__(self, verbose_name=None, name=None, upload_to=get_checkerfile_storage_path, storage=None, **kwargs):
        # increment filename length from 100 to 500
        kwargs['max_length'] = kwargs.get('max_length', 500)
        super(CheckerFileField, self).__init__(verbose_name, name, upload_to, storage, **kwargs)

class Checker(models.Model):
    """ A Checker implements some quality assurance.

    A Checker has four indicators:
        1. Whether it is *public* - the results are presented to the user
        2. Whether it is *required* - it must be passed for submission
        3. Whether it is *critical* - prevents further results from being displayed if it fails
        3. Whether it is *always* run on submission.

    If a Checker is not always run, it is only run if a *task_maker*
    starts the complete rerun of all Checkers. """

    id = models.BigAutoField(primary_key=True) # Django 3.2 requires a primary key for each class
    created = models.DateTimeField(auto_now_add=True)
    order = models.IntegerField(help_text = _('Determines the order in which the checker will start. Not necessary continuously!'))

    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    public = models.BooleanField(default=True, help_text = _('Test results are displayed to the submitter.'))
    required = models.BooleanField(default=False, help_text = _('The test must be passed to submit the solution.'))
    always = models.BooleanField(default=True, help_text = _('The test will run on submission time.'))
    critical = models.BooleanField(default=False, help_text = _('If this test fails, do not display further test results.'))

    results = GenericRelation("CheckerResult") # enables cascade on delete.

    class Meta:
        abstract = True
        app_label = 'checker'

    def __str__(self):
        return self.title()

    def create_result(self, env):
        """ Creates a new result.
        May be overloaded by subclasses."""
        assert isinstance(env.solution(), Solution)
        result = CheckerResult(checker=self, solution=env.solution())
        result.save() # otherwise we cannot attach artefacts to it
        return result

    def show_publicly(self, passed):
        """ Are results of this Checker to be shown publicly, given whether the result was passed? """
        return self.public

    def is_critical(self, passed):
        """ Checks if further results should not be shown, given whether the result was passed? """
        return self.critical and not passed

    def run(self, env):
        """ Runs tests in a special environment.
        Returns a CheckerResult. """
        assert isinstance(env, CheckerEnvironment)
        return self.create_result(env)

    def title(self):
        """ Returns the title for this checker category. To be overloaded in subclasses. """
        return "Prüfung"

    @staticmethod
    def description():
        """ Returns a description for this Checker.
        Overloaded by subclasses """
        return " no description "

    def requires(self):
        """ Returns the list of passed Checkers required by this checker.
        Overloaded by subclasses. """
        return []

    def clean(self):
        if self.required and (not self.show_publicly(False)): raise ValidationError("Checker is required, but failure isn't publicly reported to student during submission")


class CheckerEnvironment:
    """ The environment for running a checker. """

    def __init__(self, solution, tmpdir = None):
        """ Constructor: Creates a standard environment. """
        # Temporary build directory
        sandbox = settings.SANDBOX_DIR
        if tmpdir is None:
            self._tmpdir = file_operations.create_tempfolder(sandbox)
        else:
            self._tmpdir = tmpdir

        # Sources as [(name, content)...]
        self._sources = []
        for file in solution.solutionfile_set.all().order_by('file'):
            self._sources.append((file.path(), file.content()))
        # Submitter of this program
        self._user = solution.author
        # Executable program
        self._program = None

        # The solution
        self._solution = solution
        self._variables = {}

    def solution(self):
        """ Returns the solution being checked """
        return self._solution

    def tmpdir(self):
        """ Returns the path name of temporary build directory. """
        return self._tmpdir

    def sources(self):
        """ Returns the list of source files. [(name, content)...] """
        return self._sources

    def add_source(self, path, content):
        """ Add source to the list of source files. [(name, content)...] """
        self._sources.append((path, content))


    def user(self):
        """ Returns the submitter of this program (class User). """
        return self._user

    def program(self):
        """ Returns the name of the executable program, if already set. """
        return self._program

    def set_program(self, program):
        """ Sets the name of the executable program. """
        self._program = program

    def set_variable(self, key, value):
        """ Adds a new environment variable """
        self._variables[key] = value

    def variables(self):
        """ Returns the list of environment variables """
        return self._variables

def truncated_log(log):
    """
    Assumes log to be raw (ie: non-HTML) checker result log
    Returns a (string,Bool) pair consisting of
          * the log, truncated if appropriate, i.e.: if it is longer than settings.TEST_MAXLOGSIZE*1
          * a flag indicating whether the log was truncated
    """

    log_length = len(log)
    if log_length > settings.TEST_MAXLOGSIZE*1024:
        # since we might be truncating utf8 encoded strings here, result may be erroneous, so we explicitly replace faulty byte tokens
        # bugfix Ostfalia: do not calc settings.TEST_MAXLOGSIZE*1024/2 since this results in a float value
        # which cannot be used for indexing
        endindex = settings.TEST_MAXLOGSIZE*512 # 512 = 1024 / 2
        return (force_text('======= Warning: Output too long, hence truncated ======\n' +
                           log[0:endindex] + "\n...\n...\n...\n...\n" +
                           log[log_length-endindex:], errors='replace'), True)
    return (log, False)


class CheckerResult(models.Model):
    """ A CheckerResult returns the result of a Checker.
    It contains:
        - A flag that indicates if the check passed.
        - The title of the check.
        - The log of the run.
        - The time of the run. """

    from solutions.models import Solution

    id = models.BigAutoField(primary_key=True) # Django 3.2 requires a primary key for each class
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    checker = GenericForeignKey('content_type', 'object_id')

    passed = models.BooleanField(default=True,  help_text=_('Indicates whether the test has been passed'))
    log = models.TextField(help_text=_('Text result of the checker'))
    creation_date = models.DateTimeField(auto_now_add=True)
    runtime = models.IntegerField(default=0, help_text=_('Runtime in milliseconds'))
    internal_error = models.BooleanField(default=False,  help_text=_('Indicates whether an error occured during test exceution'))

    has_extra_log = models.BooleanField(default=False, help_text = _('Is there extra log output for feedback (Proforma)'))
    extra_log = models.TextField(default='', help_text=_('Extra log for feedback'))


    # Proforma new: for handling subtest results in ProFormA
    NORMAL_LOG = '0' # Original (old) log
    PROFORMA_SUBTESTS = '1'
    FEEDBACK_LIST_LOG = '2' # List Log
    TEXT_LOG = '3' # Plain text
    LOG_FORMAT_CHOICES = (
        (NORMAL_LOG, 'Checker_Log'),
        (PROFORMA_SUBTESTS, 'Proforma_Subtests'),
        (FEEDBACK_LIST_LOG, 'Feedback_List_Log'),
        (TEXT_LOG, 'Text_Log'),
    )
    log_format = models.CharField(
        max_length=2,
        choices=LOG_FORMAT_CHOICES,
        default=NORMAL_LOG,
    )

    # Proforma new: for sending regular expression in ProFormA response
    regexp = models.TextField(default='', help_text=_('Regular expression for evaluating log'))

    def title(self):
        """ Returns the title of the Checker that did run. """
        return self.checker.title()

    def only_title(self):
        """ Whether there is additional information (log or artefacts) """
        return not self.log and not self.artefacts.exists()

    def required(self):
        """ Checks if the Checker is *required* to be passed. """
        return self.checker.required

    def public(self):
        """ Checks if the results of the Checker are to be shown *publicly*, i.e.: even to the submitter """
        return self.checker.show_publicly(self.passed)

    def is_critical(self):
        """ Checks if further results should not be shown """
        return self.checker.is_critical(self.passed)

    def set_log(self, log,timed_out=False,truncated=False,oom_ed=False, log_format=NORMAL_LOG):
        """ Sets the log of the Checker run. timed_out and truncated indicated if appropriate error messages shall be appended  """
        if log_format == self.PROFORMA_SUBTESTS:
            # no truncation allowed for special logs
            assert not truncated

        if timed_out:
            # force text log
            self.log_format = self.TEXT_LOG
            self.set_internal_error(True)
            log = 'Timeout occured!\n' + log
        elif oom_ed:
            # force text log
            self.log_format = self.TEXT_LOG
            self.set_internal_error(True)
            log = 'Memory limit exceeded, execution cancelled.' + log
        else:
            # set new log format only in case of
            self.log_format = log_format

        if truncated:
            log = 'Output too long, truncated\n' + log

        #logger.debug('logformat: ' + log_format)
        #logger.debug('log: ' + log)
        self.log = log

    def set_extralog(self, log):
        """ Sets the extra log"""
        self.extra_log = log
        self.has_extra_log = True

    def set_regexp(self, regexp):
        """ Sets the regular expression for evaluating log. """
        self.regexp = regexp

    def set_passed(self, passed):
        """ Sets the passing state of the Checker. """
        assert isinstance(passed, int)
        self.passed = passed

    def add_artefact(self, filename, path):
        assert os.path.isfile(path)
        artefact = CheckerResultArtefact(result = self, filename=filename)
        artefact.file.save(filename, File(open(path, 'rb')))

    def set_internal_error(self, internal_error):
        """ Sets the Internbal Error state of the Checker. """
        assert isinstance(internal_error, int)
        self.internal_error = internal_error

    def is_proforma_subtests_format(self):
        """ format for ProFormA subtests """
        return self.log_format == self.PROFORMA_SUBTESTS

    def is_plaintext_format(self):
        """ plaintext format """
        return self.log_format == self.TEXT_LOG

    def is_feedback_list(self):
        """ feedback list format """
        return self.log_format == self.FEEDBACK_LIST_LOG

    def has_regexp(self):
        """ is there a regular expression stored """
        return (len(self.regexp) > 0)

def get_checkerresultartefact_upload_path(instance, filename):
    result = instance.result
    solution = result.solution
    return os.path.join(
        'SolutionArchive',
        'Task_' + str(solution.task.id),
        'User_' + solution.author.username,
        'Solution_' + str(solution.id),
        'Result_' + str(result.id),
        filename)

class CheckerResultArtefact(models.Model):

    id = models.BigAutoField(primary_key=True) # Django 3.2 requires a primary key for each class
    result = models.ForeignKey(CheckerResult, related_name='artefacts', on_delete=models.CASCADE)
    filename = models.CharField(max_length=128)
    file = models.FileField(
        upload_to = get_checkerresultartefact_upload_path,
        max_length=500,
        help_text = _('Artefact produced by a checker')
        )

    def __str__(self):
        return self.filename

    def path(self):
        return self.filename

# from http://stackoverflow.com/questions/5372934
@receiver(post_delete, sender=CheckerResultArtefact)
def solution_file_delete(sender, instance, **kwargs):
    # Pass false so FileField doesn't save the model.
    filename = os.path.join(settings.UPLOAD_ROOT, instance.file.name)
    instance.file.delete(False)
    # Remove left over empty directories
    dirname = os.path.dirname(filename)
    try:
        while os.path.basename(dirname) != "SolutionArchive":
            os.rmdir(dirname)
            dirname = os.path.dirname(dirname)
    except OSError:
        pass

def check_solution(solution, run_all = 0, debug_keep_tmp = True):
    """Builds and tests this solution."""

    # Delete previous results if the checkers have already been run
    solution.checkerresult_set.all().delete()
    
    # OSTFALIA/ProFormA each checker runs in its own sandbox
    # set up environment
    #env = CheckerEnvironment(solution)

    #solution.copySolutionFiles(env.tmpdir())
    yield from run_checks(solution, None, run_all, debug_keep_tmp)

    # Delete temporary directory
    #if not(debug_keep_tmp and settings.DEBUG):
    #    try:
    #        shutil.rmtree(env.tmpdir())
    #    except:
    #        pass

# Assumes to be called from within a @transaction.autocommit Context!!!!
def check_with_own_connection(solution,run_all = True, debug_keep_tmp = True):
    # Close the current db connection - will cause Django to create a new connection (not shared with other processes)
    # when one is needed, see https://groups.google.com/forum/#!msg/django-users/eCAIY9DAfG0/6DMyz3YuQDgJ
    connection.close()
    check_solution(solution, run_all, debug_keep_tmp)

    # Don't leave idle connections behind
    connection.close()

def check_with_own_connection_rev(run_all, debug_keep_tmp, solution):
    return check_with_own_connection(solution, run_all, debug_keep_tmp)


def check_multiple(solutions, run_secret = False, debug_keep_tmp = False):
    if settings.NUMBER_OF_TASKS_TO_BE_CHECKED_IN_PARALLEL <= 1:
        for solution in solutions:
            solution.check_solution(run_secret, debug_keep_tmp)
    else:
        check_it = partial(check_with_own_connection_rev, run_secret, debug_keep_tmp)

        pool = Pool(processes=settings.NUMBER_OF_TASKS_TO_BE_CHECKED_IN_PARALLEL)  # Check n solutions at once
        pool.map(check_it, solutions, 1)
        connection.close()



def delete_sandbox(dir):
    def handle_rmtree_Error(func, path, exc_info):
        if not os.path.exists(path):
            # logger.debug('failed => removed in meantime 1: ' + path)
            # racing? nothing to be done
            return
        # logger.debug('failed => try deleting ' + path)

        # Check if file access issue
        if not os.access(path, os.W_OK):
            # Try to change the permision of file
            # os.chown(path, 999, 999) # no permissions for that!
            # call the calling function again
            # func(path)
            if os.path.isdir(path):
                # use rm -rf instead of rmdir in order to delete more files :-)
                # logger.debug('rm -rf ')
                result = execute_command("sudo -E -u tester rm -rf " + path)
            else:
                # logger.debug('rm')
                result = execute_command("sudo -E -u tester rm " + path)
            # exitcode = os.waitstatus_to_exitcode(result)
            if result != 0:
                logger.error('Cannot delete file or path ' + path)
                logger.debug('os.system ' + str(result))
        else:
            logger.error('Cannot delete ' + path + ', no access')

    try:
        logger.debug('delete sandbox '+ dir)
        shutil.rmtree(dir, onerror=handle_rmtree_Error)
    except:
        logger.debug('could not delete sandbox ' + dir)
        logger.debug("Unexpected error:", sys.exc_info()[0])


def run_checks(solution, env, run_all, debug_keep_tmp=True):
    """  """

    passed_checkers = set()
    checkers = solution.task.get_checkers()

    solution_accepted = True
    solution.warnings = False
    for checker in checkers:
        if (checker.always or run_all):
            # OSTFALIA/ProFormA each checker runs in its own sandbox
            if checker.__class__.__name__ == 'CreateFileChecker':
                # CreateFileChecker is not an actual checker => skip
                logger.debug('skip CreateFileChecker')
                continue

            if checker.__class__.__name__ == 'ProFormAChecker':
                # ?? why do we have such a checker here
                logger.debug('skip ProFormAChecker')
                continue

            logger.debug('=> run check ' + checker.__class__.__name__)
            try:
                yield "data: prepare test\n\n"
                env = CheckerEnvironment(solution)

                solution.copySolutionFiles(env.tmpdir())

                # Check dependencies -> This requires the right order of the checkers
                can_run_checker = True
                for requirement in checker.requires():
                    passed_requirement = False
                    for passed_checker in passed_checkers:
                        passed_requirement = passed_requirement or issubclass(passed_checker, requirement)
                    can_run_checker = can_run_checker and passed_requirement

                start_time = time.time()

                if can_run_checker:
                    # Invoke Checker
                    # if settings.DEBUG or 'test' in sys.argv:
                    yield "data: run test\n\n"
                    result = checker.run(env)
                    #else:
                    #    try:
                    #        result = checker.run(env)
                    #    except Exception as inst:
                    #        logger.exception(inst)
                    #        result = checker.create_result(env)
                    #        result.set_log("The Checker caused an unexpected internal error: " + str(inst))
                    #        result.set_passed(False)
                    #        logger.debug('Exception caught and result set to failed')
                    #        #TODO: Email Admins
                else:
                    # make non passed result
                    # this as well as the dependency check should propably go into checker class
                    yield "data: dependent test failed\n\n"
                    result = checker.create_result(env)
                    result.set_log("Checker konnte nicht ausgeführt werden, da benötigte Checker nicht bestanden wurden.")
                    result.set_passed(False)

                elapsed_time = time.time() - start_time
                result.runtime = int(elapsed_time*1000)
                result.log = result.log.replace("\x00", "")
                result.save()

                if not result.passed and checker.show_publicly(result.passed):
                    if checker.required:
                        solution_accepted = False
                    else:
                        solution.warnings= True

                if result.passed:
                    passed_checkers.add(checker.__class__)
            except Exception as inst: # do we need that?
                raise inst
            finally:
                # Delete temporary directory
                if not(debug_keep_tmp): #  and settings.DEBUG):
                    delete_sandbox(env.tmpdir())


    solution.accepted = solution_accepted
    solution.save()
