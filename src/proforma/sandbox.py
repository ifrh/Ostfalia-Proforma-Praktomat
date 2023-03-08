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
from utilities.safeexec import execute_command

from django.conf import settings

import logging

logger = logging.getLogger(__name__)

# overlay in container with native kernel overlay only works
# when container is run in privileged mode which we want to avoid.
# Therefore fuse filesystem is used.
use_overlay = True
use_squash_fs = False

class SandboxTemplate:
    def __init__(self, praktomat_test):
        self._test = praktomat_test
        logger.debug(self._test._checker.proforma_id)

    def get_template_path(self):
        """ return root of all templates. """
        return 'Templates'

    def compress_to_squashfs(self, templ_dir):
        # create compressed layer
        logger.debug('create compressed layer')
        execute_command('ls -al ' +  templ_dir)
        # SandboxTemplate.execute_command("mksquashfs " + templ_dir + " " + templ_dir + '.sqfs')
        rc = subprocess.run(["mksquashfs", templ_dir, templ_dir + '.sqfs'],
                            cwd=os.path.join(settings.UPLOAD_ROOT, 'Templates'))
        if rc.__class__ == 'CompletedProcess':
            logger.debug(rc.returncode)

        # delete temporary folder
        logger.debug('delete temp folder ' + templ_dir)
        shutil.rmtree(templ_dir)

        # prepare for later use
        execute_command('mkdir -p ' + templ_dir)
        execute_command("squashfuse -o  allow_other " + templ_dir + '.sqfs ' + templ_dir)
        execute_command('ls -al ' +  templ_dir)

    def compress_to_archive(self, templ_dir):
        cmd = "tar -chzf " + templ_dir + ".tar ."
#        cmd = "cd " + templ_dir + " && tar -chzf " + templ_dir + ".tar ."
        execute_command(cmd, templ_dir)

#        rc = subprocess.run(["tar", "-ch", "-f=" + templ_dir + '.tar', templ_dir])
#        if rc.__class__ == 'CompletedProcess':
#            logger.debug(rc.returncode)
        # delete temporary folder
        logger.debug('delete temp folder')
        shutil.rmtree(templ_dir)





class PythonSandboxTemplate(SandboxTemplate):
    def __init__(self, praktomat_test):
        super().__init__(praktomat_test)

    def get_python_path(self):
        """ return root of all templates. """
        return 'Templates/Python'

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

    def create(self):
        requirements_txt = self._test._checker.files.filter(filename='requirements.txt', path='')
        if len(requirements_txt) > 1:
            raise Exception('more than one requirements.txt found')
        if len(requirements_txt) == 0:
            requirements_txt = None
        else:
            requirements_txt = requirements_txt.first()

        templ_dir = self._create_venv()
        logger.debug('Template dir is ' + templ_dir)

        # install modules from requirements.txt if available
        if requirements_txt is not None:
            logger.debug('install requirements')
            path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))
            # rc = subprocess.run(["ls", "-al", "bin/pip"], cwd=os.path.join(templ_dir, '.venv'))
            env = {}
            env['PATH'] = env['VIRTUAL_ENV'] = os.path.join(templ_dir, '.venv')
            rc = subprocess.run(["bin/python", "bin/pip", "install", "-r", path], cwd=os.path.join(templ_dir, '.venv'), env=env)
            if rc.__class__ == 'CompletedProcess':
                logger.debug(rc.returncode)

        pythonbin = os.readlink('/usr/bin/python3')
        logger.debug('python is ' + pythonbin)  # expect python3.x
        # copy python interpreter into sandbox
        # logger.debug('copy /usr/bin/' + pythonbin + ' => ' + templ_dir + '/' + pythonbin)
        # copy_file('/usr/bin/' + pythonbin, templ_dir + '/' + pythonbin)
        # copy python libs
        createlib = "(cd / && tar -chf - usr/lib/" + pythonbin + ") | (cd " + templ_dir + " && tar -xf -)"
        execute_command(createlib, shell=True)

        logger.debug('copy shared libraries from os')
        self._include_shared_object('libffi.so', templ_dir)
        self._include_shared_object('libffi.so.7', templ_dir)
        self._include_shared_object('libbz2.so.1.0', templ_dir)

        logger.debug('copy all shared libraries needed for python to work')
        self._test._checker.copy_shared_objects(templ_dir)

        # compile python code (smaller)
        import compileall
        import glob
        logger.debug('compile')
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
                self.compress_to_squashfs(templ_dir)
            else:
                # simply do nothing
                pass
        else:
            self.compress_to_archive(templ_dir)

    def _create_venv(self):
        # create virtual environment for reuse
        python_dir = os.path.join(settings.UPLOAD_ROOT, self.get_python_path())

        if not os.path.isfile(python_dir + '.tar'):
            venv_dir = os.path.join(python_dir, ".venv")
            # create python environment in separate folder in order to be able to reuse it
            logger.debug('create venv for reuse in ' + venv_dir)

            venv.create(venv_dir, system_site_packages=False, with_pip=True, symlinks=False)
            # install xmlrunner
            logger.debug('install xmlrunner')
            rc = subprocess.run(["bin/pip", "install", "unittest-xml-reporting"], cwd=venv_dir)
            if rc.__class__ == 'CompletedProcess':
                logger.debug(rc.returncode)

            # compile python code (smaller)
            import compileall
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

            self.compress_to_archive(python_dir)

        logger.debug('reuse python env')
        templ_dir = os.path.join(settings.UPLOAD_ROOT, self._test._checker.get_template_path())
        execute_command("mkdir -p " + templ_dir)
        execute_command("tar -xf " + python_dir + ".tar ", templ_dir)

        return templ_dir


class SandboxInstance:
    def __init__(self, proformAChecker):
        self._checker = proformAChecker

    # def _getTask(self):
    #     return self._task
    # object = property(_getTask)
    ARCHIVE = 1
    OVERLAY = 2

    def _create_from_archive(self, templ_dir, studentenv):
        self._type = self.ARCHIVE
        self._destfolder = studentenv.tmpdir()
        cmd = "cd " + studentenv.tmpdir() + " && tar -xf " + templ_dir + ".tar "
        execute_command(cmd)
        return studentenv

    def delete(self):
        pass



class PythonSandboxInstance(SandboxInstance):
    def __init__(self, proformAChecker):
        super().__init__(proformAChecker)

    def _create_from_overlay(self, templ_dir, studentenv):
        self._type = self.OVERLAY
        if not os.path.isdir(templ_dir):
            raise Exception('no sandbox template available: ' + templ_dir)

        mergeenv = CheckerEnvironment(studentenv.solution())
        # workdir = mergeenv.tmpdir() + '/work'
        # execute_command('mkdir -p ' + workdir)
        # logger.debug('workdir is ' + workdir)

        logger.debug('merge dir is ' + mergeenv.tmpdir())
        self._destfolder = mergeenv.tmpdir()

        # cmd = 'fuse-overlayfs -o lowerdir=' + templ_dir + ',upperdir=' + studentenv.tmpdir() + ',workdir=' + workdir + ' ' + mergeenv.tmpdir()
        cmd = "unionfs-fuse -o cow,relaxed_permissions,allow_other " + ' ' + studentenv.tmpdir() + '=RW:' + templ_dir + '=RO ' + mergeenv.tmpdir()
        execute_command(cmd)
        # fuse-overlayfs -o lowerdir=/work/lower,upperdir/work/upper,workdir=/work/work /work/merge
        #            cmd = 'fuse-overlayfs -o lowerdir=' + templ_dir + ',upperdir' + =up,workdir=workdir merged

        return mergeenv


    def create(self, studentenv):

        templ_dir = os.path.join(settings.UPLOAD_ROOT, self._checker.get_template_path())
        if use_overlay:
            rc =  self._create_from_overlay(templ_dir, studentenv)
        else:
            rc =  self._create_from_archive(templ_dir, studentenv)
            # allow tester to write into sandbox (after creation)
            execute_command("chmod g+w " + studentenv.tmpdir())

        return rc

    def __del__(self):
        if use_overlay:
            logger.debug('cleanup sandbox')
            execute_command('fusermount -u  ' + self._destfolder)
            execute_command('rm -rf  ' + self._destfolder)

        else:
            logger.debug('cleanup sandbox')
            execute_command('cd ' + self._destfolder + ' && rm -rf *.pyc && rm -rf .venv')

        super().delete()