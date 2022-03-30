This is the source distribution of Ostfalia-Praktomat, a programming course manager which can also be used as a simple
grading backend for different programming languages.

The code is a fork (2019) from the KIT Praktomat (https://github.com/KITPraktomatTeam/Praktomat).
It adds the ProFormA interface (https://github.com/ProFormA/proformaxml) which enables Praktomat
to be used as a grading backend in learning management systems.

The ProFormA format for tasks is 2.0 and 2.0.1 with some limitations.
The ProFormA format for HTTP request and response is 2.0 and 2.1. 

The code is currently only used as a 'docker composition'.
So the installation manual for a plain Linux server is not up-to-date, 
but you can follow the Dockerfile. 

#### Programming Languages

The following programming languages and test frameworks are provided with the ProFormA interface.

| Language     |             Test Frameworks             |
| :---:        |:---------------------------------------:|         
| Java 17      | JUnit 4.12/5, Checkstyle 8.23/8.29/10.1 |
| C++          |         Googletest, Make/CMake          |
| C            |      Googletest, CUnit, Make/CMake      |
| Python 3.8   |     Unittest (Doctest preparation)      |
| SetlX        |        Simple test, Syntax Check        |


For running SetlX tests (https://randoom.org/Software/SetlX/) you need to copy the `setlx-2.7.x.jar` 
into the extra folder.


#### Submission types

The following types of submission are supported:

* one single file (embedded or attached to request) 
* several files (embedded or attached to request) 
* zip file containing several files
* URI of SVN repository to export the submission from (credentials are stored in .env file)
 


## Installation

ProFormA Praktomat requires
 
* docker (https://docs.docker.com/engine/install/) and 
* docker-compose (https://docs.docker.com/compose/install/). 

#### Configuration

##### Mandatory: Credentials

Create an .env file containing credentials and other private data. 
A sample file is included as .env.example.  

    cp .env.example .env 

Modify credentials!

##### Optional: Change Locale

By default Praktomat uses German locale which results in German Checkstyle messages.
In order to adjust the locale settings, you can override the build argument LOCALE in the
docker-compose.yml file. E.g. for American English set LOCALE to en_US.UTF-8: 

    build:
        ...
        args:
            LOCALE: en_US.UTF-8


##### Optional: HTTPS
For enabling HTTPS (port 443) you must 

* `docker-compose.yml`: comment in `- /data/certs:/etc/nginx/certs` under `nginx`
* put your certificate files into `/data/certs` (or adjust folder name in `docker-compose.yml`)
* `nginx/nginx.conf`: comment in 443 configuration
* `nginx/nginx.conf`: set servername and adjust certificate file names  

##### Optional: Different Test Framework Versions

For using other test framework versions then you need to modify the following files:
- URLs in Dockerfile
- src/checker/checker/JUnitChecker.py
- src/checker/checker/CheckStyleChecker.py
- src/settings/docker.py

##### Optional: SetlX

The SetlX library is not installed automatically.
It can be downloaded from https://randoom.org/Software/SetlX/. 
The jar file must be copied into the `extra` subfolder and renamed to `setlX-2.7.jar`. 

#### Create Docker Containers

In order to build and start the docker composition simply run 

    docker-compose build
    docker-compose up
      
        

## ProFormA API (CURL)

<!--
TODO: The Web-Interface seems to be buggy.  

Then Praktomat is available on port 80 in your web browser:  

        http://localhost

For login see the credentials in your docker-compose.yml file (SUPERUSER and PASSWORD).

-->

The grading service is available on port 80  

        http://localhost/api/v2/submissions

and port 8010 (circumventing the web server)

        http://localhost:8010/api/v2/submissions
        

A typical grading HTTP request in CURL is

    curl -X POST --form submission.xml=@submission.xml -F "{solutionfilename}=@{solutionfile}" -F "{taskfilename}=@{taskfile}" http://localhost:8010/api/v2/submissions

with the following 'submission.xml'


    <?xml version="1.0" encoding="utf-8"?>
    <submission xmlns="urn:proforma:v2.0">
        <external-task uuid="{UUID}">http-file:{taskfilename}</external-task>
        <external-submission>http-file:{solutionfilename}</external-submission>
        <lms url="{your URI}">
            <submission-datetime>{timestamp}</submission-datetime>
            <user-id>{user id}</user-id>
            <course-id>{course id}</course-id>
        </lms>
        <result-spec format="xml" structure="separate-test-feedback" lang="de">
            <student-feedback-level>{level}</student-feedback-level>
            <teacher-feedback-level>{level}</teacher-feedback-level>
        </result-spec>
    </submission>"

`submission.xml` can be transferred as a separate file or simply as data.
Files are sent as multipart/form-data. The task file can be a zipped file or a simple xml file. 

Note that embedding the student submission file(s) into `submission.xml` as `embedded-txt-file` or 
`embedded-bin-file` is also possible.

A sample for a timestamp is:

        2019-04-03T01:01:01+01:00


#### Submission with more than one file

For submitting more than one file you have the following options:

1. create a list of embedded text or/and binary files in the `files` section in `submission.xml`.
2. external-submission: set `http-file` as file name list (comma separated without blanks) and use standard file upload
3. external-submission: compress all student submission files to a zip archive (with or without package paths for Java) 
and set `http-file` to appropriate filename.

Sample for http-file for Java submission files list:

        http-file:de/ostfalia/sample/User.java,de/ostfalia/sample/File.java

You can also omit the relative path for Java source files:

        http-file:User.java,File.java

## LON-CAPA API

Since 4.5.0 an HTTP interface for the legacy learning management system LON-CAPA is provided. 

The URI is
    
    /api/v2/loncapasubmission

The following form fields are expected:
* `submission_filename`: Submission filename
* `task`: base64 coded ProFormA task 
* `task_filename`: Filename of ProFormA task

The student submission is automatically put by LON-CAPA into `LONCAPA_student_response`.


## Maintenance

The Praktomat stores tasks and results in a database and in the filesystem. In order not to
run out of disk space the whole system should be reset from time to time (e.g. before starting a new semester).
This can easily be done by calling 

    docker-compose down
    docker-dompose up 
  
There is no need to back-up anything!

### Software Update

In case of a software update this is the recommended process:

1. `docker-compose down`
2. update software (e.g. `git pull`)
3. `docker-dompose build`    
4. `docker-dompose up` 
