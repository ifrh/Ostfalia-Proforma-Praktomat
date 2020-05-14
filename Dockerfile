# debian does not run with this dockerfile
# FROM debian:jessie
# FROM debian:buster
FROM ubuntu:xenial
# ubuntu 18.04 is very slow so we stay at 16
# FROM ubuntu:bionic

MAINTAINER Ostfalia

ENV PYTHONUNBUFFERED 1

# for praktomat itself
RUN apt-get update && apt-get install -y locales && locale-gen de_DE.UTF-8

# change locale to something UTF-8
# RUN apt-get install -y locales && locale-gen de_DE.UTF-8 
ENV LANG de_DE.UTF-8
ENV LC_ALL de_DE.UTF-8


# do not use Python 3.7 because of incompatibility with eventlet
# https://github.com/eventlet/eventlet/issues/592
# do not use Python 3.8 because of expected incompatibility with Praktomat (safeexec-Popen with preexec_fn and threads)
# https://docs.python.org/3/library/subprocess.html
# install Python 3.6 (is not faster than 3.5) => stay at 3.5
# RUN apt-get update && apt-get install -y software-properties-common && add-apt-repository ppa:deadsnakes/ppa && \
#    apt-get update && apt install -y python3.6 && \
#    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 1


RUN apt-get update && apt-get install -y swig libxml2-dev libxslt1-dev python3-pip libpq-dev locales wget cron netcat
#RUN apt-get update && apt-get install -y swig libxml2-dev libxslt1-dev python3 python3-pip libpq-dev locales wget cron netcat


# Java:
# install OpenJDK (for Java Compiler checks)
# install OpenJFK for GUI tests (for Java JFX tasks)
RUN apt-get update && apt-get install -y default-jdk openjfx
#RUN apt-get update && apt-get install -y openjdk-8-jdk openjfx
 

# SVN (delete if you do not want to access submissions from SVN repository)
RUN apt-get update && apt-get install -y subversion





 
RUN mkdir /praktomat
WORKDIR /praktomat
ADD requirements.txt /praktomat/
RUN pip3 install --upgrade pip
RUN pip3 --version
RUN pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir
#RUN pip3 install --upgrade chardet 
#RUN pip3 install gunicorn[eventlet]
#######RUN pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir && pip install --upgrade chardet && pip install gunicorn[eventlet]
# gunicorn is used for async processing


ADD . /praktomat

RUN mkdir -p /praktomat/upload


# COPY src/ src/
# COPY extra extra/
# COPY media media/


# clean packages
###### RUN apt-get clean
###### RUN rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/*
# && apt-get autoremove -y

# create cron job for deleting temporary files
COPY cron.conf /etc/cron.d/praktomat-cron
#RUN chmod 0644 /etc/cron.d/praktomat-cron
RUN crontab /etc/cron.d/praktomat-cron

# add JAVA test specific libraries
# Checkstyle
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.23/checkstyle-8.23-all.jar /praktomat/lib/
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.29/checkstyle-8.29-all.jar /praktomat/lib/
# JUnit4 runtime libraries
ADD https://github.com/junit-team/junit4/releases/download/r4.12/junit-4.12.jar /praktomat/lib/
RUN wget http://www.java2s.com/Code/JarDownload/hamcrest/hamcrest-core-1.3.jar.zip && apt-get install unzip -y && unzip -n hamcrest-core-1.3.jar.zip -d /praktomat/lib
# JUnit 5
ADD https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.6.0/junit-platform-console-standalone-1.6.0.jar /praktomat/lib/

RUN pip3 list

# run entrypoint.sh
ENTRYPOINT ["/praktomat/entrypoint.sh"]


