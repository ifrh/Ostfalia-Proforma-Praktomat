# FROM ubuntu:jammy
FROM python:3.11.9-slim-bookworm

MAINTAINER Ostfalia


# set locale
ARG LOCALE_PLAIN=de_DE
ARG LOCALE=${LOCALE_PLAIN}.UTF-8

# this is how to set locale for debian (from https://hub.docker.com/_/debian):
RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/* \
	&& localedef -i ${LOCALE_PLAIN} -c -f UTF-8 -A /usr/share/locale/locale.alias ${LOCALE}

ENV LANG ${LOCALE}
ENV LC_ALL ${LOCALE}
ENV LANGUAGE ${LOCALE}

ARG GROUP_ID=999
ARG PRAKTOMAT_ID=999

# create user with less capabilties
RUN groupadd -g ${GROUP_ID} praktomat \
    && useradd -g ${GROUP_ID} -u ${PRAKTOMAT_ID} praktomat -s /bin/bash

# Install C, cmake, Googletest (must be compiled)
# pkg-config can be used to locate gmock (and other packages) after installation
RUN apt-get update  \
    && apt-get install -y cmake libcunit1 libcunit1-dev googletest pkg-config build-essential \
    && mkdir -p /tmp/googletest \
    && cd /tmp/googletest \
    && cmake /usr/src/googletest  \
    && cmake --build .  \
    && cmake --install .  \
    && cd / \
    && rm -rf /tmp/googletest \
    && rm -rf /var/lib/apt/lists/*

# create sandbox folder and copy framework files into it
WORKDIR /sandbox

ADD framework /sandbox

# prepare sandbox folder: 
# - set permissions
RUN chmod -R 777 /sandbox


# RUN apt-get update && apt-get -y install sudo strace && adduser praktomat sudo


# change user
USER praktomat

# run entrypoint.sh as user praktomat
# CMD ["sleep", "10000"]
# ENTRYPOINT ["tail", "-f", "/dev/null"]
