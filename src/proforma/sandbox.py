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
# functions for importing ProFormA tasks into Praktomat database

import os
from . import task
import venv
import subprocess
import shutil
from checker.basemodels import CheckerEnvironment
from utilities.file_operations import copy_file
from utilities.safeexec import execute_command, execute_arglist

from django.conf import settings

import logging

logger = logging.getLogger(__name__)

# overlay in container with native kernel overlay only works
# when container is run in privileged mode which we want to avoid.
# Therefore fuse filesystem is used.
use_overlay    = True
use_squash_fs  = True
compile_python = False

class SandboxTemplate:
    def __init__(self, praktomat_test):
        self._test = praktomat_test
        logger.debug(self._test._checker.proforma_id)

    def get_template_path(self):
        """ return root of all templates. """
        return 'Templates'

    def template_exists(self, path):
        if use_overlay:
            if use_squash_fs:
                return os.path.isfile(path + '.sqfs')
            else:
                # simply do nothing
                return os.path.isdir(path)
        else:
            return os.path.isfile(path + '.tar')

    def _compress_to_squashfs(self, templ_dir):
        # create compressed layer
        logger.debug('create compressed layer')
        # execute_command('ls -al ' +  templ_dir)
        execute_command("mksquashfs " + templ_dir + ' ' + templ_dir + '.sqfs',
                        cwd=os.path.join(settings.UPLOAD_ROOT, 'Templates'))

        # delete temporary folder
        logger.debug('delete temp folder ' + templ_dir)
        shutil.rmtree(templ_dir)

    def _compress_to_archive(self, templ_dir):
        cmd = "tar -chzf " + templ_dir + ".tar ."
        execute_command(cmd, templ_dir)
        # delete temporary folder
        logger.debug('delete temp folder')
        shutil.rmtree(templ_dir)

    def _include_shared_object(self, filename, newdir):
        from pathlib import Path
        found = False
        for path in Path('/').rglob(filename):
            found = True
            logger.debug(newdir)
            logger.debug(str(path))
            logger.debug(newdir + str(path))
            copy_file(str(path), newdir + str(path))
            return

        if not found:
            raise Exception(filename + ' not found for testing')


class PythonSandboxTemplate(SandboxTemplate):
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
            print('Modules: ' + '\n'.join(modules))
            md5 = hashlib.md5('\n'.join(modules).encode('utf-8')).hexdigest()
            return md5

    def get_python_path():
        """ return root of all templates. """
        return 'Templates/Python'

    def check_preconditions(self):
        requirements_txt = self._test._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) > 1:
            raise Exception('more than one requirements.txt found')

    def create(self):
        self.check_preconditions()
        requirements_txt = self._test._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) == 0:
            requirements_txt = None
            requirements_path = None
        else:
            requirements_txt = requirements_txt.first()
            requirements_path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))

        templ_path = PythonSandboxTemplate.get_python_template_path(requirements_path)
        if self.template_exists(templ_path):
            # already exists => return
            return

        templ_dir = self._create_venv(templ_path)
        logger.debug('Template dir is ' + templ_dir)

        try:
            # install modules from requirements.txt if available
            if requirements_txt is not None:
                hash = PythonSandboxTemplate.get_hash(requirements_path)
                print(hash)
                logger.debug('install requirements')
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
                if exitcode != 0:
                    raise Exception('Cannot install requirements.txt: \n\n' + output)


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
            self._test._checker.copy_shared_objects(templ_dir)

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

            if use_overlay:
                if use_squash_fs:
                    self._compress_to_squashfs(templ_dir)
                else:
                    # simply do nothing
                    pass
            else:
                self._compress_to_archive(templ_dir)
        except:
            # try and delete complete templ_dir
            shutil.rmtree(templ_dir, ignore_errors=True)
            raise


    def get_python_template_path(requirements_path):
        """ returns the template pathname for the given requirements.txt """
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
        # templ_dir = os.path.join(settings.UPLOAD_ROOT, self._test._checker.get_template_path())
        execute_command("mkdir -p " + templ_dir)
        execute_command("tar -xf " + python_dir + ".tar ", templ_dir)

        return templ_dir


class SandboxInstance:
    def __init__(self, proformAChecker):
        self._checker = proformAChecker
    ARCHIVE = 1
    OVERLAY = 2

    def _create_from_archive(self, templ_dir, studentenv):
        self._type = self.ARCHIVE
        self._destfolder = studentenv.tmpdir()
        execute_command("tar -xf " + templ_dir + ".tar", studentenv.tmpdir())
        # allow tester to write into sandbox (after creation)
        execute_command("chmod g+w " + studentenv.tmpdir())
        return studentenv

    def _create_from_overlay(self, templ_dir, studentenv):
        self._type = self.OVERLAY

        # prepare for later use
        if use_squash_fs:
            if not os.path.isfile(templ_dir + '.sqfs' ):
                raise Exception('no sandbox template available: ' + templ_dir + '.sqfs')
            my_templ_env = CheckerEnvironment(studentenv.solution())
            self.my_templ_dir = my_templ_env.tmpdir()
            execute_command("squashfuse -o  allow_other " + templ_dir + '.sqfs ' + self.my_templ_dir)
            # execute_command('ls -al ' +  self.my_templ_dir)
            templ_dir = self.my_templ_dir
        else:
            if not os.path.isdir(templ_dir):
                raise Exception('no sandbox template available: ' + templ_dir)

        mergeenv = CheckerEnvironment(studentenv.solution())

        logger.debug('merge dir is ' + mergeenv.tmpdir())
        self._destfolder = mergeenv.tmpdir()

        cmd = "unionfs-fuse -o cow,relaxed_permissions,allow_other " + ' ' + studentenv.tmpdir() + '=RW:' + templ_dir + '=RO ' + mergeenv.tmpdir()
        execute_command(cmd)
        # fuse-overlayfs -o lowerdir=/work/lower,upperdir/work/upper,workdir=/work/work /work/merge
        #            cmd = 'fuse-overlayfs -o lowerdir=' + templ_dir + ',upperdir' + =up,workdir=workdir merged

        return mergeenv

    def create(self, templ_dir, studentenv):
        if use_overlay:
            return self._create_from_overlay(templ_dir, studentenv)
        else:
            return self._create_from_archive(templ_dir, studentenv)

    def __del__(self):
        if self._type == self.OVERLAY:
            logger.debug('cleanup sandbox')
            execute_command('fusermount -u  ' + self._destfolder)
            execute_command('rm -rf  ' + self._destfolder)
            if use_squash_fs:
                # unmount squashfs template
                execute_command('umount ' + self.my_templ_dir)
        else:
            logger.debug('cleanup sandbox')
            execute_command('rm -rf *.pyc', self._destfolder)
            execute_command('rm -rf .venv', self._destfolder)



class PythonSandboxInstance(SandboxInstance):
    def __init__(self, proformAChecker):
        super().__init__(proformAChecker)

    def create(self, studentenv):
        requirements_txt = self._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) > 1:
            raise Exception('more than one requirements.txt found')
        if len(requirements_txt) == 0:
            requirements_txt = None
            path = None
        else:
            requirements_txt = requirements_txt.first()
            path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))

        templ_dir = PythonSandboxTemplate.get_python_template_path(path)
        return super().create(templ_dir, studentenv)

