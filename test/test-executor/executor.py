# coding=utf-8

import docker
import os
import time
import tarfile

debug= False

remote_command = "python3 /sandbox/run_suite.py"
remote_result_subfolder = "__result__"
remote_result_folder = "/sandbox/" + remote_result_subfolder
local_task_folder = "task"
local_solution_folder = "solution"
local_result_file = remote_result_subfolder + "/unittest_results.xml"

def start_container():
    client = docker.from_env()

    start_time = time.time()
    # print(client.version())

    #image, build_logs = client.images.build(**your_build_kwargs)
    #for chunk in build_logs:
    #    if 'stream' in chunk:
    #        for line in chunk['stream'].splitlines():
    #            log.debug(line)

    # print(client.images.list())


    if debug:
        print("*** create container")
    # start_time = time.time()
    #volumes = ['/home/karin/docker/docker-sandbox-executor/solution/:/solution']
    volumes = [] # todo
    # with the init flag set to True signals are handled properly so that 
    # stopping the container is much faster
    container = client.containers.create(image="python-praktomat_sandbox", volumes=volumes, init=True)
    if container == None:
        raise Exception('could not create container')    
    # print("--- create docker container  %s seconds ---" % (time.time() - start_time))
    # print(container)


    if debug:
        print("** start container")
    # start_time = time.time()
    container.restart()
    # print("--- start docker container  %s seconds ---" % (time.time() - start_time))
    return container

def run_test(container):
    if debug:
        print("** create tar files")

    if not os.path.exists(local_task_folder):
        raise Exception("subfolder " + local_task_folder + " does not exist")
    if not os.path.exists(local_solution_folder):
        raise Exception("subfolder " + local_solution_folder + " does not exist")    
  
    if len(os.listdir(local_task_folder)) == 0: 
        raise Exception("subfolder " + local_task_folder + " is empty")
    if len(os.listdir(local_solution_folder)) == 0: 
        raise Exception("subfolder " + local_solution_folder + " is empty")

    # start_time = time.time()
    with tarfile.open("task.tar", 'w:gz') as tar:
        tar.add(local_task_folder, arcname=".", recursive=True)    
    with tarfile.open("solution.tar", 'w:gz') as tar:
        tar.add(local_solution_folder, arcname=".", recursive=True)    

    if debug:
        print("** upload to sandbox")        
    with open('task.tar', 'rb') as fd:
        if not container.put_archive(path='/sandbox', data=fd):
            raise Exception('cannot put task-archive.tar')
    with open('solution.tar', 'rb') as fd:
        if not container.put_archive(path='/sandbox', data=fd):
            raise Exception('cannot put solution-archive.tar')
    #print("---upload tar files  %s seconds ---" % (time.time() - start_time))

    # print(container.logs().decode('UTF-8').replace('\n', '\r\n'))
    if debug:
        print("** run tests in sandbox")    
    start_time = time.time()
    code, str = container.exec_run(remote_command, user="praktomat")
    if code != 0:
        print(str.decode('UTF-8').replace('\n', '\r\n'))
        raise Exception("running test failed")
    
    print("---run test  %s seconds ---" % (time.time() - start_time))
    if debug:
        print(code)
        print("Test run log")
        print(str.decode('UTF-8').replace('\n', '\r\n'))


def get_result(container):
    # print("** get logs")
    # print(container.logs().decode('UTF-8').replace('\n', '\r\n'))

    if debug:
        print("** stop container")
    #start_time = time.time()
    container.stop()
    #print("--- stop %s seconds ---" % (time.time() - start_time))
    start_time = time.time()

    if debug:
        print("** get result")
    tar, dict = container.get_archive(remote_result_folder)
    if debug:
        print(dict)

    with open("result.tar", 'bw') as f:
        for block in tar:
            f.write(block)
    if debug:
        print("** extract and list result")

    with tarfile.open("result.tar", 'r') as tar:
        tar.extractall()

    if debug:
        os.system("ls -al")
        os.system("ls -al " + remote_result_subfolder)
    if os.path.exists(local_result_file):
        print("TEST RESULT AVAILABLE")
    else:
        print("NO TEST RESULT AVAILABLE")


    if debug:
        print("** remove container")
    return "todo read result"

def close(container):
    container.remove()


total_start_time = time.time()
container = start_container()
try:
    run_test(container)
    result = get_result(container)
    print(result)
finally:
    close(container)
    print("---total time  %s seconds ---" % (time.time() - total_start_time))
