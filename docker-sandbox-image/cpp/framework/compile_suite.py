# coding=utf-8

import subprocess
import os
import sys

# result_folder = "__result__"
extensions = ('.c', '.C', '.hxx', '.hpp', '.h', '.cpp', '.cxx', '.o', '.a',
              'CMakeCache.txt', 'Makefile', 'makefile', 'CMakeLists.txt', 'cmake_install.cmake')


def compile_make(sandbox_dir):
    # compile CMakeLists.txt
    if os.path.exists(sandbox_dir + '/CMakeLists.txt'):
        # print('cmakefile found, execute cmake')
        # cmake .
        # cmake --build .
        if subprocess.call(['cmake', '.'], cwd=sandbox_dir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) != 0:
            # repeat call in order to get output
            subprocess.run(['cmake', '.'], cwd=sandbox_dir, stderr=subprocess.STDOUT)
            exit(1)
        if subprocess.call(['cmake', '--build', '.'], cwd=sandbox_dir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) != 0:
            subprocess.run(['cmake', '--build', '.'], cwd=sandbox_dir, stderr=subprocess.STDOUT)
            exit(1)

#        [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['cmake', '.'], sandbox_dir, unsafe=True)
#        if exitcode != 0:
#            return self.handle_compile_error(env, output, error, timed_out, oom_ed)
#        [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['cmake', '--build', '.'], sandbox_dir,
#                                                                       unsafe=True)
#        if exitcode != 0:
#            return self.handle_compile_error(env, output, error, timed_out, oom_ed)
    else:
        # run make
        # print('make')
        if subprocess.call(['make'], cwd=sandbox_dir) != 0:
            subprocess.run(['make'], cwd=sandbox_dir, stderr=subprocess.STDOUT)
            exit(1)

        # [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['make'], sandbox_dir, unsafe=True)
        # if exitcode != 0:
        #     # suppress as much information as possible
        #     # call make twice in order to get only errors in student code
        #     [output, error, exitcode, timed_out, oom_ed] = execute_arglist(['make'], sandbox_dir, unsafe=True)
        #     if error != None:
        #         # delete output when error text exists because output contains a lot of irrelevant information
        #         # for student
        #         # logger.error(error)
        #         output = error
        #         error = ''
        #     return self.handle_compile_error(env, output, error, timed_out, oom_ed)
        #


def delete_source_files(start_folder, extensions):
    # delete python files in order to prevent leaking testcode to student (part 2)
    for dirpath, dirs, files in os.walk(start_folder):
        for folder in dirs:
            # print(folder)
            for dirpath, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(extensions):
                        try:
                            # print(os.path.join(dirpath, file))
                            os.unlink(os.path.join(dirpath, file))
                        except:
                            pass
        break

    for dirpath, dirs, files in os.walk(start_folder):
        for file in files:
            # print(file)
            if file.lower().endswith(extensions):
                try:
                    # print(os.path.join(dirpath, file))
                    os.unlink(os.path.join(dirpath, file))
                except:
                    pass
        break


sandbox_dir = '.'
compile_make(sandbox_dir)
delete_source_files(sandbox_dir, extensions)





