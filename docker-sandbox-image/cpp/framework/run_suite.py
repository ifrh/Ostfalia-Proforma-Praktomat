# coding=utf-8
import signal
import subprocess
import os
import sys


sandbox_dir = '.'

# os.system("ls -al " + sandbox_dir)
# os.system("cd .. && ls -al")  

exec_command = sys.argv[1:]
if isinstance(exec_command, list):
    cmd = exec_command
    cmd.append('--gtest_output=xml')
else:
    cmd = [exec_command, '--gtest_output=xml']

# print(exec_command)
try:
    completed_process = subprocess.run(cmd, cwd=sandbox_dir,
                                       stderr=subprocess.STDOUT,
                                       universal_newlines=True,
                                       check=True)
except subprocess.CalledProcessError as e:
    import sys
    sys.tracebacklimit = 0
    # command may be invalid
    if e.returncode < 0:
        print('Signal:\r\n' + signal.strsignal(- e.returncode))
    exit(e.returncode)
except FileNotFoundError as e:
    import sys
    sys.tracebacklimit = 0
    # command may be invalid
    print(e)
    exit(1)


# os.system("ls -al " + sandbox_dir)

exit(completed_process.returncode)



