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
from utilities.safeexec import execute_command, execute_arglist

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
            yield 'python template already exists\r\n'
            # already exists => return
            return

        yield 'create virtual python environment\r\n'
        templ_dir = self._create_venv(templ_path)
        logger.info('Create Python template ' + templ_dir)

        try:
            # install modules from requirements.txt if available
            if requirements_txt is not None:
                hash = PythonSandboxTemplate.get_hash(requirements_path)
                print(hash)
                yield 'install requirements\r\n'
                logger.info('install requirements')
                # rc = subprocess.run(["ls", "-al", "bin/pip"], cwd=os.path.join(templ_dir, '.venv'))
                env = {}
                env['PATH'] = env['VIRTUAL_ENV'] = os.path.join(templ_dir, '.venv')
    #            execute_command("bin/python bin/pip install -r " + requirements_path,
    #                            cwd=os.path.join(templ_dir, '.venv'), env=env)

                (output, error, exitcode, timed_out, oom_ed) = \
                    execute_arglist(["bin/python", "bin/pip", "install", "-r", requirements_path],
                                    working_directory=os.path.join(templ_dir, '.venv'),
                                     environment_variables=env, unsafe=True)
                logger.debug(output)
                logger.debug(error)
                if output is not None:
                    yield str(output)
                    yield '\r\n'
                if error is not None:
                    yield str(error)
                    yield '\r\n'
                if exitcode != 0:
                    yield 'Cannot install requirements.txt\n\n'
                    raise Exception('Cannot install requirements.txt: \n\n' + output)

            yield 'add missing libraries \r\n'
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

            yield 'freeze template\r\n'
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




