# coding=utf-8

import unittest
import xmlrunner
import compileall
import os
import contextlib
import io

result_folder = "__result__"

# def compile_test_code(start_folder):
#     """ compile test code in order to remove it before testing """
#     import compileall
#     for dirpath, dirs, files in os.walk(start_folder):
#         # print(dirpath)
#         # print(dirs)
# #        dirs = filter(lambda folder: folder not in [".venv", "lib", "lib64", "usr", "tmp"], dirs)
#         # print(dirs)
#         for folder in dirs:
#             # print("compile folder " + folder)
#             # if not compileall.compile_dir(os.path.join(env.tmpdir(), folder), quiet=True):
#             #    logger.error('could not compile ' + folder)
#             command = "python3 -m compileall " + start_folder + "/" + folder
#             exitcode = os.system(command)
#             # exitcode = subprocess.run(['python3', '-m', 'compileall', folder], cwd=start_folder)
#             if exitcode != 0:
#                 print(exitcode)
#                 # could not compile.
#                 # TODO: run without compilation in order to generate better output???
#                 regexp = '(?<filename>\/?(\w+\/)*(\w+)\.([^:]+)),(?<line>[0-9]+)'
#                 # regexp = '(?<filename>\/?(\w+\/)*(\w+)\.([^:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?: (?<msgtype>[a-z]+): (?<text>.+)(?<code>\s+.+)?(?<position>\s+\^)?(\s+symbol:\s*(?<symbol>\s+.+))?'
#                 #return self.handle_compile_error(env, output, error, timed_out, oom_ed, regexp)
#                 raise Exception("compilation failed of folder " + folder + " failed")
#
#         for file in files:
#             # print("compile file " + file)
#             command = "python3 -m compileall " + start_folder + "/" + file
#             exitcode = os.system(command)
#             # exitcode = subprocess.run(['python3', '-m', 'compileall', file], cwd=start_folder)
#             if exitcode != 0:
#                 print(exitcode)
#                 # could not compile.
#                 # TODO: run without compilation in order to generate better output???
#                 regexp = '(?<filename>\/?(\w+\/)*(\w+)\.([^:]+)),(?<line>[0-9]+)'
#                 # regexp = '(?<filename>\/?(\w+\/)*(\w+)\.([^:]+)):(?<line>[0-9]+)(:(?<column>[0-9]+))?: (?<msgtype>[a-z]+): (?<text>.+)(?<code>\s+.+)?(?<position>\s+\^)?(\s+symbol:\s*(?<symbol>\s+.+))?'
#                 #return self.handle_compile_error(env, output, error, timed_out, oom_ed, regexp)
#                 raise Exception("compilation failed of file "+ file + " failed")
#
#
#         # only upper level => break
#         break
#         return None

def delete_py_files(start_folder):
    # delete python files in order to prevent leaking testcode to student (part 2)
    for dirpath, dirs, files in os.walk(start_folder):
        # dirs = filter(lambda folder: folder not in [".venv", "lib", "lib64", "usr", "tmp"], dirs)
        for folder in dirs:
            # print(folder)
            for dirpath, dirs, files in os.walk(folder):
                for file in files:
                    if file.endswith('.py'):
                        try:
                            # print(os.path.join(dirpath, file))
                            os.unlink(os.path.join(dirpath, file))
                        except:
                            pass
        break
                            
    for dirpath, dirs, files in os.walk(start_folder):
        for file in files:
            # print(file)
            if file.endswith('.py'):
                try:
                    # print(os.path.join(dirpath, file))
                    os.unlink(os.path.join(dirpath, file))
                except:
                    pass
        break      
                  



# os.system("ls -al")                        
# os.system("cd .. && ls -al")  


loader = unittest.TestLoader()
start_dir = '.'
suite = loader.discover(start_dir, "*test*.py")

# os.system("python3 -m compileall " + start_dir + " -q")
# if not compileall.compile_dir(start_dir, quiet=1):
#    raise Exception('could not compile ' + start_dir)

# compile_test_code(start_dir)
delete_py_files(start_dir)

os.makedirs(result_folder, exist_ok=True)
with open(result_folder + '/unittest_results.xml', 'wb') as output:
    with io.StringIO() as buf:
        # run the tests
        # ensure stdout and stderr are in correct order
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            runner = xmlrunner.XMLTestRunner(output=output, stream=buf, outsuffix='')
            #unittest.TextTestRunner(stream=buf).run(suite)
            runner.run(suite)

        print(buf.getvalue())

