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

# change locale to somethin UTF-8 
# RUN apt-get install -y locales && locale-gen de_DE.UTF-8 
ENV LANG de_DE.UTF-8
ENV LC_ALL de_DE.UTF-8

#install python 3.7 which is faster than 3.5 (installed by default)
RUN apt-get update && apt-get install -y software-properties-common && add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && apt install -y python3.7 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 1

RUN apt-get update && apt-get install -y swig libxml2-dev libxslt1-dev python3-pip libpq-dev locales wget cron netcat
#RUN apt-get update && apt-get install -y swig libxml2-dev libxslt1-dev python3 python3-pip libpq-dev locales wget cron netcat


# Java:
# install OpenJDK (only needed if you want to run Java Compiler checker)
# install OpenJFK for GUI tests
RUN apt-get update && apt-get install -y default-jdk openjfx
#RUN apt-get update && apt-get install -y openjdk-8-jdk openjfx
 



# && apt-get autoremove -y


 
RUN mkdir /praktomat
WORKDIR /praktomat
ADD requirements.txt /praktomat/
RUN pip3 install --upgrade pip
RUN pip3 --version
RUN pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir
RUN pip3 install --upgrade chardet 
RUN pip3 install gunicorn[eventlet]
#######RUN pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir && pip install --upgrade chardet && pip install gunicorn[eventlet]
# gunicorn is used for async processing


ADD . /praktomat

RUN mkdir -p /praktomat/upload


# COPY src/ src/
# COPY extra extra/
# COPY media media/

# remove staticfiles, otherwise we get problems with collectstatic later on
# RUN pip uninstall staticfiles


# clean packages
###### RUN apt-get clean
###### RUN rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/*

# create cron job for deleting temporary files
COPY cron.conf /etc/cron.d/praktomat-cron
#RUN chmod 0644 /etc/cron.d/praktomat-cron
RUN crontab /etc/cron.d/praktomat-cron

# JAVA test specific libraries
# Checkstyle
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.23/checkstyle-8.23-all.jar /praktomat/lib/
# JUnit4 runtime libraries
ADD https://github.com/junit-team/junit4/releases/download/r4.12/junit-4.12.jar /praktomat/lib/
RUN wget http://www.java2s.com/Code/JarDownload/hamcrest/hamcrest-core-1.3.jar.zip && apt-get install unzip -y && unzip -n hamcrest-core-1.3.jar.zip -d /praktomat/lib
# JUnit 5
ADD https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.6.0/junit-platform-console-standalone-1.6.0.jar /praktomat/lib/
# run entrypoint.sh
ENTRYPOINT ["/praktomat/entrypoint.sh"]


