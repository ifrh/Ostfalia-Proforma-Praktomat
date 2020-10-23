# debian does not run with this dockerfile
# FROM debian:jessie
# FROM debian:buster
# FROM ubuntu:xenial
# ubuntu 18.04 is very slow so we stay at 16
#FROM ubuntu:bionic
# Ubuntu 20.10
FROM ubuntu:groovy

MAINTAINER Ostfalia

ENV PYTHONUNBUFFERED 1
ENV PASSWORD=123
# set locale to German (UTF-8)
ARG LOCALE=de_DE.UTF-8

# change locale to something UTF-8
RUN apt-get update && apt-get install -y locales && locale-gen ${LOCALE}
ENV LANG ${LOCALE}
ENV LC_ALL ${LOCALE}


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

# ADD UNIX USERS
################

# install sudo
RUN apt-get update && apt-get -y install sudo

# create group praktomat
RUN groupadd -g 999 praktomat

# add user praktomat (uid=999)
RUN useradd -g 999 -u 999 praktomat -s /bin/sh --no-create-home -c "Praktomat Demon" && \
   usermod -aG sudo praktomat && \
   echo "praktomat:$PASSWORD" | sudo chpasswd

# add user tester (uid=1000)
RUN useradd -g 999 -u 1000 tester -s /bin/false --no-create-home -c "Test Exceution User"

# allow user praktomat to execute 'sudo -u tester ...'
# allow user praktomat to start cron
RUN echo "praktomat ALL=NOPASSWD:SETENV: /usr/sbin/cron,/usr/bin/py3clean,/usr/bin/python3" >> /etc/sudoers && \
echo "praktomat ALL=(tester) NOPASSWD: ALL" >> /etc/sudoers


RUN mkdir /praktomat && chown 999:999 /praktomat
WORKDIR /praktomat
ADD --chown=999:999 requirements.txt /praktomat/
RUN pip3 install --upgrade pip
RUN pip3 --version
RUN pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir


ADD . /praktomat

RUN mkdir -p /praktomat/upload


# COPY src/ src/
# COPY extra extra/
# COPY media media/


# clean packages
###### RUN apt-get clean
###### RUN rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/*
# && apt-get autoremove -y

# create cron job for deleting temporary files (no dots in new filename)
COPY cron.conf /etc/cron.d/praktomat-cron
#COPY --chown=999:999 cron.conf /etc/cron.d/praktomat-cron
#RUN chmod 0644 /etc/cron.d/praktomat-cron

# add JAVA test specific libraries
# Checkstyle
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.23/checkstyle-8.23-all.jar /praktomat/lib/
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.29/checkstyle-8.29-all.jar /praktomat/lib/
# JUnit4 runtime libraries
ADD https://github.com/junit-team/junit4/releases/download/r4.12/junit-4.12.jar /praktomat/lib/
RUN wget http://www.java2s.com/Code/JarDownload/hamcrest/hamcrest-core-1.3.jar.zip && apt-get install unzip -y && unzip -n hamcrest-core-1.3.jar.zip -d /praktomat/lib
# JUnit 5
ADD https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.6.1/junit-platform-console-standalone-1.6.1.jar /praktomat/lib/

RUN pip3 list
RUN python3 --version
RUN java -version

# set permissions
RUN chmod 0644 /praktomat/lib/* /praktomat/extra/*

# install debugging tools
# RUN apt-get -y install strace less nano

# run entrypoint.sh as user praktomat
USER praktomat
ENTRYPOINT ["/praktomat/entrypoint.sh"]


