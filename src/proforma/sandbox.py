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

from django.conf import settings

import logging

logger = logging.getLogger(__name__)

class SandboxTemplate:
    def __init__(self, praktomat_test):
        self._test = praktomat_test
        logger.debug(self._test._checker.proforma_id)

    def compress_to_squashfs(self, templ_dir):
        # create compressed layer
        logger.debug('create compressed layer')
        rc = subprocess.run(["mksquashfs", templ_dir, templ_dir + '.sqfs'],
                            cwd=os.path.join(settings.UPLOAD_ROOT, 'Templates'))
        if rc.__class__ == 'CompletedProcess':
            logger.debug(rc.returncode)

        # delete temporary folder
        logger.debug('delete temp folder')
        shutil.rmtree(templ_dir)

        # prepare for later use
        os.system('mkdir -p ' + templ_dir)
        rc = subprocess.run(["squashfuse", templ_dir + '.sqfs', templ_dir])
        if rc.__class__ == 'CompletedProcess':
            logger.debug(rc.returncode)

    def compress_to_archive(self, templ_dir):
        cmd = "cd " + templ_dir + " && tar -chzf " + templ_dir + ".tar ."
        print(cmd)
        os.system(cmd)

#        rc = subprocess.run(["tar", "-ch", "-f=" + templ_dir + '.tar', templ_dir])
#        if rc.__class__ == 'CompletedProcess':
#            logger.debug(rc.returncode)
        # delete temporary folder
        logger.debug('delete temp folder')
        shutil.rmtree(templ_dir)


class PythonSandboxTemplate(SandboxTemplate):
    def __init__(self, praktomat_test):
        super().__init__(praktomat_test)

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
        requirements_txt = requirements_txt.first()

        # create virtual environment

        templ_dir = os.path.join(settings.UPLOAD_ROOT, self._test._checker.get_template_path())
        venv_dir = os.path.join(templ_dir, ".venv")
        logger.debug('create venv in ' + venv_dir)
        venv.create(venv_dir, system_site_packages=False,with_pip=True, symlinks=False)

        # install xmlrunner
        logger.debug('install xmlrunner')
        rc = subprocess.run(["bin/pip", "install", "unittest-xml-reporting"], cwd=venv_dir)
        if rc.__class__ == 'CompletedProcess':
            logger.debug(rc.returncode)

        # install modules from requirements.txt if available
        if requirements_txt is not None:
            logger.debug('install requirements')
            path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))
            logger.debug(path)
            rc = subprocess.run(["bin/pip", "install", "-r", path], cwd=venv_dir)
            if rc.__class__ == 'CompletedProcess':
                logger.debug(rc.returncode)

        pythonbin = os.readlink('/usr/bin/python3')
        logger.debug('python is ' + pythonbin)  # expect python3.x
        # copy python interpreter into sandbox
        logger.debug('copy /usr/bin/' + pythonbin + ' => ' + templ_dir + '/' + pythonbin)
        copy_file('/usr/bin/' + pythonbin, templ_dir + '/' + pythonbin)
        # copy python libs
        createlib = "(cd / && tar -chf - usr/lib/" + pythonbin + ") | (cd " + templ_dir + " && tar -xf -)"
        logger.debug(createlib)
        os.system(createlib)

        logger.debug('copy shared libraries from os')
        self._include_shared_object('libffi.so', templ_dir)
        self._include_shared_object('libffi.so.7', templ_dir)
        self._include_shared_object('libbz2.so.1.0', templ_dir)

        logger.debug('copy all shared libraries needed for python to work')
        self._test._checker.copy_shared_objects(templ_dir)

        # self.compress_to_squashfs(templ_dir)
        self.compress_to_archive(templ_dir)


class SandboxInstance:
    def __init__(self, proformAChecker):
        self._checker = proformAChecker

    # def _getTask(self):
    #     return self._task
    # object = property(_getTask)

    def delete(self):
        pass


class PythonSandboxInstance(SandboxInstance):
    def __init__(self, proformAChecker):
        super().__init__(proformAChecker)

    def _create_from_squashfs(self, templ_dir, studentenv):
        mergeenv = CheckerEnvironment(studentenv.solution())
        workdir = mergeenv.tmpdir() + '/work'
        os.system('mkdir -p ' + workdir)
        logger.debug('workdir is ' + workdir)

        logger.debug('merge dir is ' + mergeenv.tmpdir())

        cmd = 'fuse-overlayfs -o lowerdir=' + templ_dir + ',upperdir=' + studentenv.tmpdir() + ',workdir=' + workdir + ' ' + mergeenv.tmpdir()
        print(cmd)
        os.system(cmd)

        # fuse-overlayfs -o lowerdir=/work/lower,upperdir/work/upper,workdir=/work/work /work/merge
        #            cmd = 'fuse-overlayfs -o lowerdir=' + templ_dir + ',upperdir' + =up,workdir=workdir merged

        return mergeenv

    def _create_from_archive(self, templ_dir, studentenv):
        cmd = "cd " + studentenv.tmpdir() + " && tar -xf " + templ_dir + ".tar "
        logger.debug(cmd)
        os.system(cmd)

        return studentenv

    def create(self, studentenv):
        templ_dir = os.path.join(settings.UPLOAD_ROOT, self._checker.get_template_path())
        if not os.path.isdir(templ_dir):
            raise Exception('no sandbox template available: ' + templ_dir)
        return self._create_from_archive(templ_dir, studentenv)

