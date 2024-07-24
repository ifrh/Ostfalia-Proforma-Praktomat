# -*- coding: utf-8 -*-

import os
from os.path import *
import time
import subprocess
import signal
import resource
import logging


logger = logging.getLogger(__name__)

from django.conf import settings

#################
# https://gist.github.com/bofm/d8932cf04913554d8f393ba43ef30dd5
import sys
import re

#legal XML 1.0 char:
# x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
# any Unicode character, excluding the surrogate blocks, FFFE, and FFFF.
_illegal_unichrs = ((0x00, 0x08),  # #x9 | #xA
#                    (0x0B, 0x1F),
                    (0x0B, 0x0C),  # + xD
                    (0x0E, 0x1F),  # +x20-xD7FF
                    (0xD800, 0xDFFF),  # = UTF-16 reserved # # E000 - xFFFD
                    (0xFFFE, 0xFFFF), # x10000-#x10FFFF]
                    # excluded blocks: https://www.w3.org/TR/xml/#charsets
                    (0x7F, 0x84), (0x86, 0x9F),
                    (0xFDD0, 0xFDDF),
                    (0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF),
                    (0x3FFFE, 0x3FFFF), (0x4FFFE, 0x4FFFF),
                    (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
                    (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF),
                    (0x9FFFE, 0x9FFFF), (0xAFFFE, 0xAFFFF),
                    (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
                    (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF),
                    (0xFFFFE, 0xFFFFF), (0x10FFFE, 0x10FFFF))
_illegal_ranges = tuple("%s-%s" % (chr(low), chr(high))
                        for (low, high) in _illegal_unichrs
                        if low < sys.maxunicode)
_illegal_xml_chars_re = re.compile('[%s]' % ''.join(_illegal_ranges))

def escape_xml_invalid_chars(xml_text):
    return _illegal_xml_chars_re.sub('[??]', xml_text)
#################

def execute_arglist(args, working_directory, environment_variables={},
                    timeout=None, maxmem=None, fileseeklimit=None, extradirs=[], unsafe=False, error_to_output=True):
    """ Wrapper to execute Commands with the praktomat testuser. Excpects Command as list of arguments, the first being the execeutable to run. """
    assert isinstance(args, list)
    if not unsafe:
        raise Exception("Safe mode is not supported")

    command = args[:]

    # print(environment_variables)
    # print(os.getenv('PATH'))
    # do not modify environment for current process => use copy!!
    environment = os.environ.copy()
    environment.update(environment_variables)
    # print(os.getenv('PATH'))
    if fileseeklimit is not None:
        fileseeklimitbytes = fileseeklimit * 1024

    sudo_prefix = ["sudo", "-E", "-u", "tester"]

    # if unsafe:
    command = []
    # elif settings.USEPRAKTOMATTESTER:
    #     # run restrict binary which changes user to tester and limits resources
    #     # command = sudo_prefix.copy()
    #     command = ["/sbin/restrict"]
    # # elif settings.USESAFEDOCKER:
    # #     command = ["sudo", "safe-docker"]
    # #     # for safe-docker, we cannot kill it ourselves, due to sudo, so
    # #     # rely on the timeout provided by safe-docker
    # #     if timeout is not None:
    # #         command += ["--timeout", "%d" % timeout]
    # #         # give the time out mechanism below some extra time
    # #         timeout += 5
    # #     if maxmem is not None:
    # #         command += ["--memory", "%sm" % maxmem]
    # #     for d in extradirs:
    # #         command += ["--dir", d]
    # #     command += ["--"]
    # #     # ensure ulimit
    # #     if fileseeklimit:
    # #         # Doesn’t work yet: http://stackoverflow.com/questions/25789425
    # #         command += ["bash", "-c", 'ulimit -f %d; exec \"$@\"' % fileseeklimit, "ulimit-helper"]
    # #     # add environment
    # #     command += ["env"]
    # #     for k, v in environment_variables.items():
    # #         command += ["%s=%s" % (k, v)]
    # else:
    #     command = []
    command += args[:]

    logger.debug('execute command in ' + working_directory + ':')
    logger.debug('command :' + str(command))

    # TODO: Dont even read in output longer than fileseeklimit. This might be most conveniently done by supplying a file like object instead of PIPE

    def prepare_subprocess():
        # create a new session for the spawned subprocess using os.setsid,
        # so we can later kill it and all children on timeout, taken from http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
        # os.setsid()
        # Limit the size of files created during execution
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        if fileseeklimit is not None:
            resource.setrlimit(resource.RLIMIT_FSIZE, (fileseeklimitbytes, fileseeklimitbytes))
            if resource.getrlimit(resource.RLIMIT_FSIZE) != (fileseeklimitbytes, fileseeklimitbytes):
                raise ValueError(resource.getrlimit(resource.RLIMIT_FSIZE))
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if error_to_output else subprocess.PIPE,
        cwd=working_directory,
        env=environment,
        start_new_session=True # call of os.setsid()
        # preexec_fn=prepare_subprocess
    )

    timed_out = False
    oom_ed = False
    try:
        [output, error] = process.communicate(timeout=timeout)
    # except subprocess.TimeoutExpired:
    # Ostfalia: this specific exception is raised but is not caught that way (I do not know why!).
    # So we catch every exception and check for type name
    except Exception as e:
        logger.error("exception occured:" + str(type(e)))
        if str(type(e) == str(subprocess.TimeoutExpired)):
        # if (type(e) == subprocess.TimeoutExpired):
            logger.debug("TIMEOUT")
            timed_out = True

        # kill session
        term_cmd = ["pkill", "-TERM", "-s", str(process.pid)]
        kill_cmd = ["pkill", "-KILL", "-s", str(process.pid)]
        if not unsafe and settings.USEPRAKTOMATTESTER:
            # negative pid means process group
            # restrict used
            term_cmd = ["kill", "-TERM", "-" + str(process.pid)]
            kill_cmd = ["kill", "-SIGKILL", "-" + str(process.pid)]
            term_cmd = sudo_prefix + ["-n"] + term_cmd
            kill_cmd = sudo_prefix + ["-n"] + kill_cmd

        print(term_cmd)
        returncode = subprocess.call(term_cmd)
        logger.debug("kill returned " + str(returncode))
        if process.poll() == None:
            time.sleep(5)
            logger.debug("force kill: " + str(kill_cmd))
            # os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            returncode = subprocess.call(kill_cmd)
            logger.debug("force kill returned " + str(returncode))

            # if not unsafe and settings.USEPRAKTOMATTESTER:
            #    # restrict used
            #    group = os.getpgid(process.pid)
            #    logger.error("try and kill process group " + str(group))
            #    os.killpg(group, signal.SIGTERM)


        [output, error] = process.communicate()
        if not timed_out:
            raise # no timeout

    # proforma: remove invalid xml char
    return [escape_xml_invalid_chars(output.decode('utf-8')), error, process.returncode, timed_out, oom_ed]



def execute_command(command, cwd=None, shell=False, env=None):
    """ simple wrapper for subprocess.run for running non-safe commands """
    if not shell:
        if type(command) != list:
            logger.debug(command)
            command = command.split()
        else:
            logger.debug(' '.join(command))

    # execute
    rc = subprocess.run(command, shell=shell, check=True, cwd=cwd, env=env)
    if type(rc).__name__ != 'CompletedProcess':
        logger.debug(rc.__class__)
        raise Exception('do not know how to handle return code ' + type(rc).__name__)

    if rc.returncode == 0:
        # everything is fine
        return rc.returncode

    logger.debug(rc.returncode)
    raise Exception('command failed: ' + ' '.join(command))
