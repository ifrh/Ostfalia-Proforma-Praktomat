# Python

## Python Unittests: 

The tests run in a virtual Python environment, in which Python packages can be installed by
simply adding a requirements.txt to the task.

The environment is set up the first time a test case is run. Usually this is when the task creator 
tries submitting a model solution.

Since some of the packages have to be downloaded from the Internet and then installed,
this setup may take longer than the grading timeout in Moodle.
In general, however, the setup should be completed despite an error message due to a timeout.
So please just try again.

Most Python packages will run without any further action. However, it cannot be ruled out that
individual packages require additional packages from the operating system.

Limits:

Inner classes with tests in Python unit tests will not be tested (Problem of Python Unittest framework)

## Python Doctest: 

Does not support creating a virtual environemnt by adding a requirements.txt.

# Googletest

pkg-config is available for locating gtest and gmock. A valid CMakeList.txt file could look like this:

        cmake_minimum_required(VERSION 3.14)
        project(runTests)

        # GoogleTest requires at least C++11
        set(CMAKE_CXX_STANDARD 11)

        ## Locate GTest and GMock
        find_package(PkgConfig REQUIRED)

        pkg_check_modules(GTEST REQUIRED gtest)
        pkg_check_modules(GMOCK REQUIRED gmock)

        include_directories(
                ${GTEST_INCLUDE_DIRS}
                ${GMOCK_INCLUDE_DIRS}
        )

        ## Link runTests with libraries
        add_executable(runTests tests.cpp x.cpp)
        target_link_libraries(runTests ${GTEST_LIBRARIES} ${GMOCK_LIBRARIES} pthread)


Alternative CMakeList.txt file for gtest only:

        cmake_minimum_required(VERSION 3.14)
        project(runTests)
 
        # Locate GTest
        find_package(GTest REQUIRED)
        include_directories(${GTEST_INCLUDE_DIRS})
 
        # Link runTests with what we want to test and the GTest and pthread library
        add_executable(runTests tests.cpp)
        target_link_libraries(runTests ${GTEST_LIBRARIES} pthread)