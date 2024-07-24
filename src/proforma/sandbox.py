# -*- coding: utf-8 -*-

# This file is part of Ostfalia-Praktomat.
#
# Copyright (C) 2024 Ostfalia University
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

from math import floor
import sys
from django.conf import settings
import docker
import tarfile
from abc import ABC, abstractmethod
import os
import tempfile
import random
import glob

# import requests => for Timeout Exception

import logging

logger = logging.getLogger(__name__)

# approach:
# 1. create container from image
# 1.a. python: upload and install requirements
# 1.b. python: commit new image (and reuse later for tests with same requirements.txt)
# 2 upload task files and student files
# 3 compile
# 4 commit container to temporary image
# 5 run tests with run command detached
# 6 wait for exit of container
# 7 get result file

# working without commit and using exec_run is faster but wait does not work with exec_run :-(

debug_sand_box = False


def delete_dangling_container(client, name):
    if debug_sand_box:
        logger.debug("delete dangling container " + name)
    try:
        # Note: we have to add a status. Otherwise only running containes will be delivered
        # and the container will probably not be running
        containers = client.containers.list(filters={"name": name, "status": "created"})
        if len(containers) == 0:
            containers = client.containers.list(filters={"name": name, "status": "exited"})
        if len(containers) == 0:
            containers = client.containers.list(filters={"name": name, "status": "exited"})
        if len(containers) == 0:
            containers = client.containers.list(filters={"name": name, "status": "restarting"})
        if len(containers) == 0:
            containers = client.containers.list(filters={"name": name, "status": "running"})
        if len(containers) == 0:
            logger.error("FATAL: cannot find dangling container " + name)

        # print(containers)
        for container in containers:
            if container.name != name:
                continue

            if debug_sand_box:
                logger.debug("Stop dangling container " + container.name)
            try:
                container.stop()
            except Exception as e:
                logger.debug("cannot stop dangling container " + container.name)
                logger.debug(e)
            try:
                if debug_sand_box:
                    logger.debug("Remove dangling container " + container.name)
                container.remove(force=True)
            except Exception as e:
                logger.debug("cannot remove dangling container " + container.name)
                logger.debug(e)
    except Exception as e1:
        logger.error(e1)


class DockerSandbox(ABC):
    # remote_command = "python3 /sandbox/run_suite.py"
    # remote_result_subfolder = "__result__"
    # remote_result_folder = "/sandbox/" + remote_result_subfolder
    millisec = 1000000
    sec = millisec * 1000
    default_cmd = 'tail -f /dev/null'
    meg_byte = 1024 * 1024

    def __init__(self, client, studentenv,
                 compile_command, run_command, download_path):
        if debug_sand_box:
            logger.debug('__init__')

        self._client = client
        self._studentenv = studentenv
        self._compile_command = compile_command
        self._run_command = run_command
        self._download_path = download_path
        self._container = None
        self._image = None
        self._healthcheck = {
            "test": [],  # ["CMD", "ls"],
            "interval": (DockerSandbox.sec * 1),  # 500000000, # 500ms
            "timeout": (DockerSandbox.sec * 1),  # 500000000, # 500ms
            "retries": 1,
            "start_period": (DockerSandbox.sec * 3),  # 1000000000 # start after 1s
        }
        self._mem_limit = DockerSandbox.meg_byte * settings.TEST_MAXMEM_DOCKER_DEFAULT

    def __del__(self):
        """ remove container
        """
        # return # for testing
        if debug_sand_box:
            logger.debug('__del__')
        if hasattr(self, '_container') and self._container is not None:
            try:
                # try and stop container
                if debug_sand_box:
                    logger.debug('stop container')
                self._container.stop()
            except Exception as e:
                # ignore error if failed
                logger.error(e)

            try:
                # try and remove container
                if debug_sand_box:
                    logger.debug('remove container')
                self._container.remove(force=True)
            except Exception as e:
                logger.error(e)
        if hasattr(self, '_image') and self._image is not None:
            try:
                if debug_sand_box:
                    logger.debug('remove (temporary) image')
                self._image.remove(force=True)
            except Exception as e:
                logger.error(e)

        if debug_sand_box:
            logger.debug('__del__')

    def create(self, image_name):
        # with the init flag set to True signals are handled properly so that
        # stopping the container is much faster
        # self._container = self._client.containers.run(
        #     image_name, init=True,
        #     network_disabled=True,
        #     ulimits = ulimits, detach=True)

        if debug_sand_box:
            logger.debug('create container')
        self._container = self._client.containers.create(
            image_name, init=True,
            mem_limit=self._mem_limit,
            #            cpu_period=100000, cpu_quota=90000,  # max. 70% of the CPU time => configure
            network_disabled=True,
            command=DockerSandbox.default_cmd,  # keep container running
            detach=True,
            healthcheck=self._healthcheck
            #            tty=True
        )

        if self._container is None:
            raise Exception("could not create container")
        if debug_sand_box:
            logger.debug('start container')
        self._container.start()

        # self.wait_test(image_name)

    #     def wait_test(self, image_name):
    #         """ wait seems to work only with run, not with exec_run :-(
    #         """
    #         try:
    #             print("wait_test") # sleep 2 seconds
    #             # code, output = self._container.exec_run(cmd="sleep 2", user="999", detach=True)
    #             tmp_container = self._client.containers.run(image_name, command="sleep 20", user="999", detach=True)
    #
    #             try:
    #                 # wait_dict = self._container.wait(timeout=5, condition="next-exit") # timeout in seconds
    #                 wait_dict = tmp_container.wait(timeout=5) # , condition="next-exit") # timeout in seconds
    #                 print(wait_dict)
    # #            except requests.exceptions.ReadTimeout as e:
    #                 print("failed")
    #             except Exception  as e:
    #                 print("passed")
    #                 logger.error(e)
    #
    #                 tmp_container = self._client.containers.run(image_name, command="sleep 2", user="999", detach=True)
    #                 try:
    #                     # wait_dict = self._container.wait(timeout=5, condition="next-exit") # timeout in seconds
    #                     wait_dict = tmp_container.wait(timeout=5)  # , condition="next-exit") # timeout in seconds
    #                     print(wait_dict)
    #                     print("passed")
    #                 except Exception as e:
    #                     print("failed")
    #                     logger.error(e)
    #
    #             print("end of wait_test")
    #             logger.debug("end of sleep")
    #
    #         except Exception as ex:
    #             logger.error("command execution failed")
    #             logger.error(ex)

    def _get_run_timeout(self):
        """ in seconds
        """
        return settings.TEST_TIMEOUT

    def upload_environmment(self):
        if debug_sand_box:
            logger.debug('upload to container')

        if not os.path.exists(self._studentenv):
            raise Exception("subfolder " + self._studentenv + " does not exist")

        if len(os.listdir(self._studentenv)) == 0:
            raise Exception("subfolder " + self._studentenv + " is empty")

        # we need to change permissions on student folder in order to
        # have the required permissions inside test docker container
        os.system("chown -R praktomat:praktomat " + self._studentenv)

        tmp_filename = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as f:
                tmp_filename = f.name
                with tarfile.open(fileobj=f, mode='w:gz') as tar:
                    tar.add(self._studentenv, arcname=".", recursive=True)
            if debug_sand_box:
                logger.debug("** upload to sandbox " + tmp_filename)
            # os.system("ls -al " + tmp_filename)
            with open(tmp_filename, 'rb') as fd:
                if not self._container.put_archive(path='/sandbox', data=fd):
                    raise Exception('cannot put requirements.tar/' + tmp_filename)
        finally:
            if tmp_filename:
                os.unlink(tmp_filename)

    def exec(self, command):
        if debug_sand_box:
            logger.debug("exec_run in sandbox")
        logger.debug("exec: " + command)
        code, output = self._container.exec_run(command, user="praktomat")
        if debug_sand_box:
            logger.debug("exitcode is " + str(code))
        # capture output from generator
        from utilities.safeexec import escape_xml_invalid_chars
        text = escape_xml_invalid_chars(output.decode('UTF-8').replace('\n', '\r\n'))
        logger.debug(text)
        return (code == 0), text

    def compile_tests(self, command=None):
        # start_time = time.time()
        if not command is None:
            self._compile_command = command
        if self._compile_command is None:
            return True, ""
        return self.exec(self._compile_command)

    def runTests(self, command=None, safe=True, image_suffix=''):
        """
        returns passed?, logs, timnout?
        """
        if debug_sand_box:
            logger.debug("** run tests in sandbox")
        if not command is None:
            self._run_command = command
        # start_time = time.time()

        # use stronger limits for test run
        #        warning_dict = self._container.update(mem_limit="1g",
        #                               cpu_period=100000, cpu_quota=20000) # max. 20% of the CPU time => configure
        #       print(warning_dict)

        # commit intermediate container to image
        number = random.randrange(1000000000)
        self._image = self._container.commit("tmp", str(number))
        # stop old container and remove
        self._container.stop()
        self._container.remove(force=True)
        self._container = None
        print(self._image.tags)

        ulimits = [
            docker.types.Ulimit(name='CPU', soft=25, hard=30),
            docker.types.Ulimit(name='nproc', soft=250, hard=250),
            docker.types.Ulimit(name='nofile', soft=64, hard=64),
            docker.types.Ulimit(name='as', soft=self._mem_limit, hard=self._mem_limit),
            docker.types.Ulimit(name='fsize', soft=1024 * 100, hard=1024 * 100),  # 100MB
        ]

        # if self._mem_limit < 1200 * DockerSandbox.meg_byte:
        # ulimits.append(docker.types.Ulimit(name='AS', soft=self._mem_limit, hard=self._mem_limit))

        code = None
        # code, output = self._container.exec_run(cmd, user="999", detach=True)
        logger.debug("execute '" + self._run_command + "'")
        name = "tmp_" + image_suffix + str(number)
        try:
            self._container = (
                self._client.containers.run(self._image.tags[0],
                                            command=self._run_command, user="praktomat", detach=True,
                                            stdout=True,
                                            stderr=True,
                                            working_dir="/sandbox",
                                            name=name,
                                            init=True,
                                            healthcheck=self._healthcheck,
                                            mem_limit=self._mem_limit if safe else None,
                                            #                                                    cpu_period=100000, cpu_quota=90000,  # max. 40% of the CPU time => configure
                                            network_disabled=True if safe else False,
                                            # Checkstyle requires network (arrggh!)
                                            ulimits=ulimits if safe else None,
                                            ))
        except Exception as e:
            # in case of an exception there might be a dangling container left
            # that is not removed by the docker code.
            # So we look for a container named xxx and try and remove it
            # filters = { "name": "tmp_" + str(number) }
            logger.error("FATAL ERROR: cannot create new container for running command - " + name)
            logger.error(e)
            delete_dangling_container(self._client, name)
            raise e

        logger.debug("wait timeout is " + str(self._get_run_timeout()))
        try:
            wait_dict = self._container.wait(timeout=self._get_run_timeout())
            # wait_dict = self._container.wait(timeout=self._get_run_timeout())
            # print(wait_dict)
            code = wait_dict['StatusCode']
        except Exception as e:
            # probably timeout
            code = 1
            logger.error(e)
            output = self._container.logs()
            if debug_sand_box:
                logger.debug("got logs")
            text = 'Execution timed out... (Check for infinite loop in your code)'
            text += output.decode('UTF-8').replace('\n', '\r\n')
            #            text += '\r\n+++ Test Timeout +++'
            return False, text, True
        if debug_sand_box:
            logger.debug("run finished")
        output = self._container.logs()
        # capture output from generator
        text = output.decode('UTF-8').replace('\n', '\r\n')

        # import locally
        from utilities.safeexec import escape_xml_invalid_chars
        return (code == 0), escape_xml_invalid_chars(text), False

    def download_result_file(self):
        if debug_sand_box:
            logger.debug("get result")
        try:
            tar, dict = self._container.get_archive(self._download_path)
            logger.debug(dict)

            with open(self._studentenv + '/result.tar', mode='bw') as f:
                for block in tar:
                    f.write(block)
            with tarfile.open(self._studentenv + '/result.tar', 'r') as tar:
                tar.extractall(path=self._studentenv)
            os.unlink(self._studentenv + '/result.tar')

            # try and stop in order to save resources
            self._container.stop()
        except:
            pass

    # def stop(self):
    #     """ stop as soon as possible"""
    #     if hasattr(self, '_container') and self._container is not None:
    #         try:
    #             # try and stop container
    #             self._container.stop()
    #         except Exception as e:
    #             # ignore error if failed
    #             logger.error(e)


class DockerSandboxImage(ABC):
    base_tag = '0'  # default tag name

    def __init__(self, checker, dockerfile_path, image_name,
                 dockerfilename='Dockerfile'):
        self._checker = None
        # global module_init_called
        # if not module_init_called:
        #    logger.debug("constructor for sandbox of checker.proforma_id: " + self._checker.proforma_id)
        self._client = docker.from_env()
        self._tag = None
        self._dockerfile_path = dockerfile_path
        self._image_name = image_name
        self._dockerfilename = dockerfilename
        self._checker = checker

    def __del__(self):
        if hasattr(self, '_client') and self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                pass

    @abstractmethod
    def get_container(self, proformAChecker, studentenv):
        """ return an instance created from this template """
        return

    def _get_image_tag(self):
        return DockerSandboxImage.base_tag

    def _get_image_fullname(self, tag=None):
        """ return the full image name including the suffix and the tag """
        if tag is None:
            tag = self._tag

        if tag is None:
            raise ValueError("self._tag is None")

        return self._image_name + ':' + tag

    def _image_exists(self, tag):
        full_imagename = self._get_image_fullname(tag)
        logger.debug("check if image exists: " + full_imagename)
        images = self._client.images.list(filters={"reference": full_imagename})
        # print(images)
        return len(images) > 0

    def create_image(self):
        """ creates the default docker image """
        self._create_image_for_tag(self._get_image_tag())

    def _create_image_for_tag(self, tag):
        """ creates the docker image """
        if self._image_exists(tag):
            logger.debug("image for tag " + tag + " already exists")
            return

        # check
        logger.debug("create image for tag " + tag + " from " + self._dockerfile_path)
        image, logs_gen = self._client.images.build(path=self._dockerfile_path,
                                                    dockerfile=self._dockerfilename,
                                                    tag=self._get_image_fullname(tag),
                                                    rm=True, forcerm=True)
        return self._get_image_fullname(tag)


## CPP/C tests
class CppSandbox(DockerSandbox):
    def __init__(self, client, studentenv, command):
        super().__init__(client, studentenv,
                         "python3 /sandbox/compile_suite.py",  # compile command
                         "python3 /sandbox/run_suite.py " + command,  # run command
                         "/sandbox/test_detail.xml")  # download path


#    def __del__(self):
#        super().__del__()

class CppImage(DockerSandboxImage):
    def __init__(self, praktomat_test):
        super().__init__(praktomat_test,
                         '/praktomat/docker-sandbox-image/cpp',
                         "cpp-praktomat_sandbox",
                         None)

    #    def __del__(self):
    #        super().__del__()

    def get_container(self, studentenv, command):
        self.create_image()
        cpp_sandbox = CppSandbox(self._client, studentenv, command)
        cpp_sandbox.create(self._get_image_fullname(self._get_image_tag()))
        return cpp_sandbox


## Java tests
class JavaSandbox(DockerSandbox):
    def __init__(self, client, studentenv, command):
        super().__init__(client, studentenv,
                         "javac -classpath . @sources.txt",  # compile command: java
                         #                         "javac -classpath . -nowarn -d . @sources.txt",  # compile command: java
                         command,  # run command
                         None)  # download path
        self._mem_limit = DockerSandbox.meg_byte * settings.TEST_MAXMEM_DOCKER_JAVA  # increase memory limit


#   def __del__(self):
#        super().__del__()


class JavaImage(DockerSandboxImage):
    def __init__(self, praktomat_test):
        super().__init__(praktomat_test,
                         '/praktomat/docker-sandbox-image/java',
                         "java-praktomat_sandbox",
                         None)

    def get_container(self, studentenv = None, command = None):
        self.create_image()
        if studentenv is not None:
            j_sandbox = JavaSandbox(self._client, studentenv, command)
            j_sandbox.create(self._get_image_fullname(self._get_image_tag()))
            return j_sandbox
        else:
            return None


class PythonSandbox(DockerSandbox):
    remote_result_subfolder = "__result__"
    remote_result_folder = "/sandbox/" + remote_result_subfolder

    def __init__(self, container, studentenv):
        super().__init__(container, studentenv,
                         "python3 -m compileall /sandbox -q",
                         "python3 /sandbox/run_suite.py",
                         PythonSandbox.remote_result_folder)
        from django.conf import settings
        self._mem_limit = DockerSandbox.meg_byte * settings.TEST_MAXMEM_DOCKER_PYTHON  # increase memory limit

    def download_result_file(self):
        super().download_result_file()

        resultpath = self._studentenv + '/' + PythonSandbox.remote_result_subfolder + '/unittest_results.xml'
        if not os.path.exists(resultpath):
            raise Exception("No test result file found")
        os.system("mv " + resultpath + " " + self._studentenv + '/unittest_results.xml')


class PythonImage(DockerSandboxImage):
    """ python sandbox template for python tests """

    # name of python docker image
    image_name = "python-praktomat_sandbox"
    base_image_tag = image_name + ':' + DockerSandboxImage.base_tag

    def look_for_requirements_txt(path):
        filelist = glob.glob(path + '/*requirements.txt')
        if len(filelist) > 0:
            logger.debug(filelist)
            return filelist[0]
        else:
            return None

    def __init__(self, praktomat_test, requirements_path=None):
        super().__init__(praktomat_test,
                         dockerfile_path='/praktomat/docker-sandbox-image/python',
                         image_name=PythonImage.image_name,
                         #                         dockerfilename='Dockerfile.alpine',
                         dockerfilename=None)

        self._requirements_path = requirements_path

    #    def __del__(self):
    #        super().__del__()

    def yield_log(self, log):
        if log is None:
            return
        log = log.decode('UTF-8').replace('\n', '\r\n')

        lines = filter(str.strip, log.splitlines())
        for line in lines:
            yield "data: " + line + "\n\n"

    def _get_hash(requirements_txt):
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

    #    def check_preconditions(self):
    #        requirements_txt = self._checker.files.filter(filename='requirements.txt', path='')
    #        if len(requirements_txt) > 1:
    #            raise Exception('more than one requirements.txt found')

    def create_image_yield(self):
        #        """ creates the docker image """
        logger.debug("create python image (if it does not exist)")

        #        self.check_preconditions()

        tag = self._get_image_tag()
        # print("tag " + str(tag))
        if self._image_exists(tag):
            logger.debug("python image for tag " + tag + " already exists")
            yield 'data: python image for tag ' + tag + ' already exists\n\n'
            # already exists => return
            return

        # ensure base image exists
        self._create_image_for_tag(DockerSandboxImage.base_tag)

        if self._requirements_path is None:
            return

        # create container from base image, install requirements
        # and commit container to image
        # install modules from requirements.txt if available
        yield 'data: install requirements\n\n'
        logger.info('install requirements from ' + self._requirements_path)
        logger.debug('create container from ' + PythonImage.base_image_tag)
        number = random.randrange(1000000000)
        name = "tmp_python_image_" + str(number)
        try:
            container = self._client.containers.create(image=PythonImage.base_image_tag,
                                                       init=True,
                                                       command=DockerSandbox.default_cmd,  # keep container running
                                                       name=name
                                                       )

        except Exception as e:
            # in case of an exception there might be a dangling container left
            # that is not removed by the docker code.
            # So we look for a container named xxx and try and remove it
            logger.error("FATAL ERROR: cannot create new python image - " + name)
            delete_dangling_container(self._client, name)
            raise e

        tmp_filename = None
        try:
            container.start()
            # start_time = time.time()

            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as f:
                tmp_filename = f.name
                with tarfile.open(fileobj=f, mode='w:gz') as tar:
                    tar.add(self._requirements_path, arcname="requirements.txt", recursive=False)

            logger.debug("** upload to sandbox " + tmp_filename)
            # os.system("ls -al " + tmp_filename)
            with open(tmp_filename, 'rb') as fd:
                if not container.put_archive(path='/sandbox', data=fd):
                    raise Exception('cannot put requirements.tar/' + tmp_filename)

            logger.debug(container.status);
            code, log = container.exec_run("pip3 install -r /sandbox/requirements.txt", user="root")
            yield from self.yield_log(log)
            logger.debug(log.decode('UTF-8').replace('\n', '\r\n'))
            if code != 0:
                raise Exception('Cannot install requirements.txt')

            yield 'data: commit image\n\n'
            logger.debug("** commit image to " + PythonImage.image_name + ':' + tag)
            container.commit(repository=PythonImage.image_name,
                             tag=tag)
        #                             tag=PythonSandboxTemplate.image_name + ':' + tag)
        finally:
            if tmp_filename:
                os.unlink(tmp_filename)
            container.stop()
            container.remove(force=True)
            pass

    def create_image(self):
        for a in self.create_image_yield():  # function is generator, so this must be handled in order to be executed
            pass

    def _get_image_tag(self):
        if not self._tag is None:
            return self._tag

        if self._requirements_path is None:
            self._tag = super()._get_image_tag()
        else:
            self._tag = PythonImage._get_hash(self._requirements_path)

            #        requirements_txt = self._checker.files.filter(filename='requirements.txt', path='')
        #        if len(requirements_txt) > 1:
        #            raise Exception('more than one requirements.txt found')
        #        if len(requirements_txt) == 0:
        #            self._tag = super()._get_image_tag()
        #        else:
        #            requirements_txt = requirements_txt.first()
        #            requirements_path = os.path.join(settings.UPLOAD_ROOT, task.get_storage_path(requirements_txt, requirements_txt.filename))
        #            self._tag = PythonImage._get_hash(requirements_path)

        return self._tag

    def get_container(self, studentenv):
        """ return an instance created from this template """
        self.create_image()  # function is generator, so this must be handled in order to be executed
        p_sandbox = PythonSandbox(self._client, studentenv)
        p_sandbox.create(self._get_image_fullname(self._get_image_tag()))
        return p_sandbox


#    def empty_function(self):
#        return True


def cleanup():
    client = docker.from_env()
    try:
        print("deleting old containers (image tmp exited)")
        filters = {
            "status": "exited",
            "name": "tmp_*",
        }
        containers = client.containers.list(filters=filters)
        print(containers)
        for container in containers:
            try:
                if container.image.tags[0].startswith('tmp:'):
                    print("Remove container " + container.name + " image: " + container.image.tags[0])
                    container.remove(force=True)
            except Exception as e:
                print("cannot remove container " + container.name)
                print(e)
        print("ok")

        print("deleting dangling containers (image tmp created)")
        filters = {
            "status": "created",
            "name": "tmp_*",
        }
        containers = client.containers.list(filters=filters)
        print(containers)
        for container in containers:
            try:
                # no image available
                print("Remove container " + container.name)
                container.remove(force=True)
            except Exception as e:
                print("cannot remove container " + container.name)
                print(e)
        print("ok")

        print("deleting old containers (image *-praktomat_sandbox:*)")
        containers = client.containers.list(all=True)
        print(containers)
        for container in containers:
            # print(container.image.tags)
            if container.image.tags[0].find('-praktomat_sandbox:') >= 0 or \
                    container.image.tags[0].find('tmp:') >= 0:
                print("Remove container " + container.name + " image: " + container.image.tags[0])
                try:
                    container.stop()
                    container.remove(force=True)
                except Exception as e:
                    print("cannot remove container " + container.name)
                    print(e)
        #            else:
        #                print("do not delete " + container.name + " image: " + container.image.tags[0] + " state: " + container.status)
        print("ok")

        print("deleting old images")
        images = client.images.list(name="tmp")
        print(images)
        for image in images:
            if image.tags[0].startswith('tmp:'):
                print("Remove image " + image.tags[0])
                try:
                    image.remove(force=True)
                except Exception as e:
                    print(e)
                pass
        print("ok")

        print("deleting dangling images")
        try:
            client.images.prune(filters={"dangling": 1})
        except Exception as e:
            print(e)
            pass

        print("ok")
    finally:
        client.close()


def create_images():
    # create images
    print("creating docker image for java tests ...")
    sys.stdout.flush()
    sys.stderr.flush()
    JavaImage(None).create_image()
    print("done")

    print("creating docker image for python tests ...")
    sys.stdout.flush()
    sys.stderr.flush()
    for a in PythonImage(None).create_image_yield():
        pass
    print("done")
    print("creating docker image for c/C++ tests ...")
    sys.stdout.flush()
    sys.stderr.flush()
    CppImage(None).create_image()
    print("done")


def get_state():
    state = {'containers': [], 'images': []}
    client = docker.from_env()
    try:
        state['info'] = client.info()
        filters = {
            "status": "exited",
            "name": "tmp_*",
        }
        print("containers")
        containerlist = []
        for container in client.containers.list(all=True):
            containerlist.append(container)

        state['containers'] = containerlist
        print("images")

        #        images = client.images.list(name="tmp")
        # print(images)
        imagelist = []
        for image in client.images.list():
            # if image.tags[0].startswith('tmp:'):
            # print("image " + image.tags[0])
            # print(image.tags)
            # print(image.labels)
            # print(image.attrs)
            # print(image.history())
            # imagelist.append(image.tags[0])
            # print(image)
            newimage = {}
            newimage['name'] = image.tags[0]
            newimage["sizeMb"] = floor(
                float(image.attrs['Size']) / (1024.0 * 1024.0))  # int(image.attrs.Size) / (1024.0 * 1024.0)
            imagelist.append(newimage)

        state['images'] = imagelist
    except Exception:
        pass
    finally:
        client.close()

    return state


if __name__ == '__main__':
    # flush echo messages from shell script on praktomat docker startup
    sys.stdout.flush()
    sys.stderr.flush()

    cleanup()
    create_images()



