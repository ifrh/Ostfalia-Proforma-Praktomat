# -*- coding: utf-8 -*-

# This file is part of Ostfalia-Praktomat.
#
# Copyright (C) 2023 Ostfalia University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# functions for creating sandboxes

import os
import subprocess
import venv
import shutil

from . import sandbox, task
from django.conf import settings
from utilities.safeexec import execute_command, escape_xml_invalid_chars

import logging

logger = logging.getLogger(__name__)

compile_python = False


#class PythonSandboxInstance(sandbox.SandboxInstance):
#    """ sandbox instance for python tests """
#    def __init__(self):
#        super().__init__()


class PythonSandboxTemplate(sandbox.SandboxTemplate):
    """ python sandbox template for python tests """
    def __init__(self, praktomat_test):
        super().__init__(praktomat_test)

    def get_hash(requirements_txt):
        """ create simple hash for requirements.txt content """
        import hashlib
        with open(requirements_txt, 'r') as f:
            # read strip lines
            modules = [line.strip() for line in f.readlines()]
            # skip empty lines
            modules = list(filter(lambda line: len(line) > 0, modules))
            # I do not know if the order matters so I do not sort the modules!
            # Otherwise a wrong order can never be corrected.
            # modules.sort()
            # print('Modules: ' + '\n'.join(modules))
            md5 = hashlib.md5('\n'.join(modules).encode('utf-8')).hexdigest()
            return md5

    def get_python_path():
        """ return root of all templates. """
        return 'Templates/Python'

    def check_preconditions(self):
        requirements_txt = self._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) > 1:
            raise Exception('more than one requirements.txt found')

    def execute_arglist_yield(args, working_directory, environment_variables={}):
        """ yield output text during execution. """
        assert isinstance(args, list)

        command = args[:]
        # do not modify environment for current process => use copy!!
        environment = os.environ.copy()
        environment.update(environment_variables)

        logger.debug('execute command in ' + working_directory + ':')
        logger.debug('command :' + str(command))

        try:
            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=working_directory,
                env=environment,
                start_new_session=True, # call of os.setsid()
            ) as process:
                while True:
                    data = process.stdout.readline()  # Alternatively proc.stdout.read(1024)
                    if len(data) == 0:
                        break
                    yield 'data: ' + str(data) + '\n\n'
                # if it is too fast then get remainder
                remainder = process.communicate()[0]
                if remainder is not None and len(remainder) > 0:
                    yield 'data: ' + str(remainder) + '\n\n'

                # Get exit code
                result = process.wait(0)
                if result != 0:
                    # stop further execution
                    raise Exception('command exited with code <> 0')

        except Exception as e:
            if type(e) == subprocess.TimeoutExpired:
                logger.debug("TIMEOUT")
                yield 'data: timeout\n\n'
            else:
                logger.error("exception occured: " + str(type(e)))
            raise


    def create(self):
        self.check_preconditions()
        requirements_txt = self._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) == 0:
            requirements_txt = None
            requirements_path = None
        else:
            requirements_txt = requirements_txt.first()
            requirements_path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))

        templ_path = self.get_python_template_path()
        if self.template_exists(templ_path):
            yield 'data: python template already exists\n\n'
            # already exists => return
            return

        yield 'data: create virtual python environment\n\n'
        templ_dir = self._create_venv(templ_path)
        logger.info('Create Python template ' + templ_dir)

        try:
            # install modules from requirements.txt if available
            if requirements_txt is not None:
                hash = PythonSandboxTemplate.get_hash(requirements_path)
                print(hash)
                yield 'data: install requirements\n\n'
                logger.info('install requirements')
                # rc = subprocess.run(["ls", "-al", "bin/pip"], cwd=os.path.join(templ_dir, '.venv'))
                env = {}
                env['PATH'] = env['VIRTUAL_ENV'] = os.path.join(templ_dir, '.venv')
    #            execute_command("bin/python bin/pip install -r " + requirements_path,
    #                            cwd=os.path.join(templ_dir, '.venv'), env=env)

                cmd = ["bin/python", "bin/pip", "install", "-r", requirements_path]
                yield from PythonSandboxTemplate.execute_arglist_yield(cmd, os.path.join(templ_dir, '.venv'), env)

            yield 'data: add missing libraries\n\n'
            logger.info('copy python libraries from OS')
            pythonbin = os.readlink('/usr/bin/python3')
            logger.debug('python is ' + pythonbin)  # expect python3.x
            # copy python libs
            createlib = "(cd / && tar -chf - usr/lib/" + pythonbin + ") | (cd " + templ_dir + " && tar -xf -)"
            execute_command(createlib, shell=True)

            logger.debug('copy shared libraries from os')
            self._include_shared_object('libffi.so', templ_dir)
            self._include_shared_object('libffi.so.7', templ_dir)
            self._include_shared_object('libbz2.so.1.0', templ_dir)
            self._include_shared_object('libsqlite3.so.0', templ_dir)

            logger.debug('copy all shared libraries needed for python to work')
            self._checker.copy_shared_objects(templ_dir)

            # compile python code (smaller???)
            if compile_python:
                import compileall
                import glob
                logger.debug('**** compile')
                success = compileall.compile_dir(templ_dir, quiet=True)

            # delete all python source code
    #        logger.debug('delete py')
    #        for filePath in glob.glob(templ_dir + '/**/*.py', recursive=True):
    #            if 'encodings' not in filePath and 'codecs' not in filePath:
    #                print(filePath)
    #                try:
    #                    os.remove(filePath)
    #                except:
    #                    logger.error("Error while deleting file : ", filePath)
    #            else:
    #                print('**' + filePath)

            yield 'data: freeze template\n\n'
            self._commit(templ_dir)
        except:
            # try and delete complete templ_dir
            shutil.rmtree(templ_dir, ignore_errors=True)
            raise


    def get_python_template_path(self):
        """ returns the template pathname for the given requirements.txt """
        requirements_txt = self._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) > 1:
            raise Exception('more than one requirements.txt found')
        if len(requirements_txt) == 0:
            requirements_txt = None
            requirements_path = None
        else:
            requirements_txt = requirements_txt.first()
            requirements_path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))

        hash = None
        if requirements_path is not None:
            hash = PythonSandboxTemplate.get_hash(requirements_path)

        if hash is not None:
            return os.path.join(settings.UPLOAD_ROOT, PythonSandboxTemplate.get_python_path(), hash)
        else:
            return os.path.join(settings.UPLOAD_ROOT, PythonSandboxTemplate.get_python_path(), '0')



    def _create_venv(self, templ_dir):
        # create virtual environment for reuse
        python_dir = os.path.join(settings.UPLOAD_ROOT, PythonSandboxTemplate.get_python_path(), 'Python')

        if not os.path.isfile(python_dir + '.tar'):
            venv_dir = os.path.join(python_dir, ".venv")
            # create python environment in separate folder in order to be able to reuse it
            logger.debug('create venv for reuse in ' + venv_dir)

            venv.create(venv_dir, system_site_packages=False, with_pip=True, symlinks=False)
            # install xmlrunner
            logger.debug('install xmlrunner')
            rc = subprocess.run(["bin/pip", "install", "unittest-xml-reporting"], cwd=venv_dir)
            if rc.returncode != 0:
                raise Exception('cannot install unittest-xml-reporting')

            # compile python code (smaller)
            if compile_python:
                import compileall
                logger.debug('**** compile')
                success = compileall.compile_dir(venv_dir, quiet=True)

            # delete all python source code
            # logger.debug('delete py in python venv')
            # import glob
            #for filePath in glob.glob(venv_dir + '/**/*.py', recursive=True):
            #    print(filePath)
            #    try:
            #        os.remove(filePath)
            #    except:
            #        logger.error("Error while deleting file : ", filePath)

            self._compress_to_archive(python_dir)

        logger.debug('reuse python env')
        # templ_dir = os.path.join(settings.UPLOAD_ROOT, self._checker.get_template_path())
        execute_command("mkdir -p " + templ_dir)
        execute_command("tar -xf " + python_dir + ".tar ", templ_dir)

        return templ_dir

    def get_instance(self, studentenv):
        """ return an instance created from this template """
        templ_dir = self.get_python_template_path()
        if not self.template_exists(templ_dir):
            logger.debug('Template does not exist => (re)create')
            self.create()

        logger.info('Use Python template ' + templ_dir)
        instance = sandbox.SandboxInstance(templ_dir, studentenv)
        return instance




