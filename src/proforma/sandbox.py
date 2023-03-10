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
use_overlay    = True
use_squash_fs  = True

class SandboxInstance:
    ARCHIVE = 1
    OVERLAY = 2

    def __init__(self, templ_dir, studentenv):
        self._templ_dir = templ_dir
        self._studentenv = studentenv
        self._destfolder = None

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

    def create(self):
        if use_overlay:
            return self._create_from_overlay(self._templ_dir, self._studentenv)
        else:
            return self._create_from_archive(self._templ_dir, self._studentenv)

    def __del__(self):
        if self._destfolder is None:
            return

        try:
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
        except:
            # ignore errors
            pass


class SandboxTemplate:
    def __init__(self, checker):
        self._checker = checker
        logger.debug(self._checker.proforma_id)

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
        if os.path.isfile(templ_dir + '.sqfs'):
            logger.error('squashfs file already exists, try and delete with recreate')
            os.unlink(templ_dir + '.sqfs')

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

    def _commit(self, templ_dir):
        if use_overlay:
            if use_squash_fs:
                self._compress_to_squashfs(templ_dir)
            else:
                # simply do nothing
                pass
        else:
            self._compress_to_archive(templ_dir)

    def get_instance(self, proformAChecker, studentenv):
        """ return an instance created from this template """
        raise Exception('not implemented')
