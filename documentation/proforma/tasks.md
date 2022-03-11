# Python

Inner classes with tests in Python unit tests will not be tested (Problem of Python Unittest framework)

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
