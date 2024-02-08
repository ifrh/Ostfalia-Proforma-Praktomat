# debian does not run with this dockerfile
# FROM debian:jessie
# FROM debian:buster
# focal: Ubuntu 20.04 LTS
# => Python 3.8
FROM ubuntu:focal
# jammy: Ubuntu 22.04 LTS
# => Python 3.10
# FROM ubuntu:jammy

MAINTAINER Ostfalia

ENV PYTHONUNBUFFERED 1
ARG PASSWORD=123
# set locale to German (UTF-8)
ARG LOCALE=de_DE.UTF-8

ARG DEBIAN_FRONTEND=noninteractive

# change locale to something UTF-8
RUN apt-get update && apt-get install -y locales && locale-gen ${LOCALE} && rm -rf /var/lib/apt/lists/*
ENV LANG ${LOCALE}
ENV LC_ALL ${LOCALE}


# do not use Python 3.8 because of expected incompatibility with Praktomat (safeexec-Popen with preexec_fn and threads)
# https://docs.python.org/3/library/subprocess.html
# RUN apt-get update && apt-get install -y software-properties-common && add-apt-repository ppa:deadsnakes/ppa && \
#    apt-get update && apt install -y python3.6 && \
#    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 1


# libffi-dev is used for python unittests with pandas (avoid extra RUN command)
# squashfs-tools is used for sandbox templates
RUN apt-get update && \
    apt-get install -y swig libxml2-dev libxslt1-dev python3-pip python3-venv libpq-dev wget cron netcat sudo \
    subversion git unzip \
    libffi-dev && \
    rm -rf /var/lib/apt/lists/*
#RUN apt-get update && apt-get install -y swig libxml2-dev libxslt1-dev python3 python3-pip libpq-dev locales wget cron netcat

# Java:
# install OpenJDK (for Java Compiler checks)
# install OpenJFK for GUI tests (for Java JFX tasks)
# install SVN (delete if you do not want to access submissions from SVN repository)
# install cmake and cunit for testing with cunit

# RUN apt-get update && apt-get install -y default-jdk openjfx subversion cmake libcunit1 libcunit1-dev

# install Java 17 from Bellsoft
# CHANGE 'arch=amd64' to something that fits your architecture
###RUN wget -q -O - https://download.bell-sw.com/pki/GPG-KEY-bellsoft | sudo apt-key add -
###RUN echo "deb [arch=amd64] https://apt.bell-sw.com/ stable main" | sudo tee /etc/apt/sources.list.d/bellsoft.list
###RUN sudo apt-get update && apt-get install -y bellsoft-java17

# Install Java 17 and JavaFX
RUN apt-get update && apt-get install -y openjdk-17-jdk openjfx && rm -rf /var/lib/apt/lists/*
# Install C, cmake, Googletest (must be compiled)
# pkg-config can be used to locate gmock (and other packages) after installation
RUN apt-get update && apt-get install -y cmake libcunit1 libcunit1-dev googletest pkg-config && \
    mkdir -p /tmp/googletest && cd /tmp/googletest && cmake /usr/src/googletest && cmake --build . && cmake --install . && \
    rm -rf /var/lib/apt/lists/*

# ADD UNIX USERS
################

# create group praktomat
RUN groupadd -g 999 praktomat && \
# add user praktomat (uid=999) \
  useradd -g 999 -u 999 praktomat -s /bin/sh --home /praktomat --create-home --comment "Praktomat Demon" && \
  usermod -aG sudo praktomat && \
  echo "praktomat:$PASSWORD" | sudo chpasswd && \
# add user tester (uid=777) \
  useradd -g 999 -u 777 tester -s /bin/false --no-create-home -c "Test Exceution User"

# allow user praktomat to execute 'sudo -u tester ...'
# allow user praktomat to start cron
RUN echo "praktomat ALL=NOPASSWD:SETENV: /usr/sbin/cron,/usr/bin/py3clean,/usr/bin/python3,/usr/bin/mount " >> /etc/sudoers && \
echo "praktomat ALL=(tester) NOPASSWD: ALL" >> /etc/sudoers


# RUN mkdir /praktomat && chown 999:999 /praktomat
WORKDIR /praktomat
ADD --chown=999:999 requirements.txt /praktomat/
RUN pip3 install --upgrade pip && \
    pip3 --version && \
    pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir


COPY . /praktomat

RUN mkdir -p /praktomat/upload && mkdir -p /praktomat/media


# COPY src/ src/
# COPY extra extra/
# COPY media media/




# create cron job for deleting temporary files (no dots in new filename)
COPY cron.conf /etc/cron.d/praktomat-cron
#COPY --chown=999:999 cron.conf /etc/cron.d/praktomat-cron
#RUN chmod 0644 /etc/cron.d/praktomat-cron

# add JAVA test specific libraries
# Checkstyle
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-10.1/checkstyle-10.1-all.jar /praktomat/lib/
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.23/checkstyle-8.23-all.jar /praktomat/lib/
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.29/checkstyle-8.29-all.jar /praktomat/lib/
# JUnit4 runtime libraries
ADD https://github.com/junit-team/junit4/releases/download/r4.12/junit-4.12.jar /praktomat/lib/
RUN wget http://www.java2s.com/Code/JarDownload/hamcrest/hamcrest-core-1.3.jar.zip && unzip -n hamcrest-core-1.3.jar.zip -d /praktomat/lib
# JUnit 5
ADD https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.6.1/junit-platform-console-standalone-1.6.1.jar /praktomat/lib/

RUN pip3 list && python3 --version && java -version

# set permissions
RUN chmod 0644 /praktomat/lib/* /praktomat/extra/*

# compile and install restrict.c
RUN cd /praktomat/src && make restrict && sudo install -m 4750 -o root -g praktomat restrict /sbin/restrict

# install fuse for sandbox templates
# user_allow_other is needed in or der to allow praktomat user to set option allow_other on mount
RUN apt-get update && apt-get install -y fuse3 unionfs-fuse squashfs-tools squashfuse fuse-overlayfs && \
    rm -rf /var/lib/apt/lists/* && \
    sed -i -e 's/^#user_allow_other/user_allow_other/' /etc/fuse.conf
# install tree and strace for debugging :-)
#    tree strace less nano && \

# RUN apt-get update && apt-get install -y libfuse3-dev automake unzip && \
#    wget https://github.com/containers/fuse-overlayfs/archive/refs/tags/v1.9.zip && \
#    unzip v1.9.zip && \
#    cd fuse-overlayfs-1.9 && sh ./autogen.sh && ./configure && make && mv /usr/bin/fuse-overlayfs /usr/bin/fuse-overlayfs.old && \
#    mv fuse-overlayfs /usr/bin/fuse-overlayfs

# change user
USER praktomat

# run entrypoint.sh as user praktomat
ENTRYPOINT ["/praktomat/entrypoint.sh"]


