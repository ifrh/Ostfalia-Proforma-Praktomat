FROM python:3.11.9-slim-bookworm
# FROM python:3.11.9-alpine3.20

MAINTAINER Ostfalia

ENV PYTHONUNBUFFERED 1

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
ARG PRAKTOMAT_ID=1100
# ARG TESTER_ID=777

# install xmlrunner for test framework
# lxml is needed for xml result conversion
# RUN pip3 install --upgrade pip && pip3 install xmlrunner unittest-xml-reporting lxml
RUN pip3 install --upgrade pip && pip3 install xmlrunner unittest-xml-reporting 

# create user with less capabilties 
# RUN groupadd -g ${GROUP_ID} praktomat \
#    && useradd -g ${GROUP_ID} -u ${PRAKTOMAT_ID} praktomat -s /bin/bash
RUN useradd -u ${PRAKTOMAT_ID} praktomat -s /bin/bash



# create sandbox folder and copy framework files into it
WORKDIR /sandbox

COPY framework /sandbox

# prepare sandbox folder: 
# - set permissions
# - create result folder
# - create folder for matplotlib cache (suppresses warning)
RUN chmod -R 777 /sandbox \
	&& mkdir -p __result__ \
	&& chmod -R 777 __result__ \
	&& mkdir -p .matplotlib \
	&& chmod -R 777 .matplotlib

ENV MPLCONFIGDIR=/sandbox/.matplotlib

# install requirements
# ADD task /sandbox
# RUN pip3 install --upgrade pip && pip3 install -r requirements.txt


# RUN apt-get update && apt-get -y install sudo strace && adduser praktomat sudo


# change user
USER praktomat

# run entrypoint.sh as user praktomat
# CMD ["sleep", "10000"]
# ENTRYPOINT ["tail", "-f", "/dev/null"]
