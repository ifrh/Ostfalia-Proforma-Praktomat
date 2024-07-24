FROM python:3.11.9-slim-bookworm

LABEL description="Praktomat with ProFormA interface"
LABEL org.opencontainers.image.authors="Ostfalia University of Applied Sciences"

ARG PASSWORD=123

ARG GROUP_ID=999
# docker group id (name=docker cannot be used here)
# figure it out by call of "/etc/group"
ARG DOCKER_GROUP_ID=2000
ARG PRAKTOMAT_ID=1100
# ARG TESTER_ID=777


ARG DEBIAN_FRONTEND=noninteractive

# set locale
ARG LOCALE_PLAIN=de_DE
ARG LOCALE=${LOCALE_PLAIN}.UTF-8

# set environment
ENV LANG     = ${LOCALE} \
    LC_ALL   = ${LOCALE} \
    LANGUAGE = ${LOCALE} \
    PYTHONUNBUFFERED = 1


# this is how to set locale for debian (from https://hub.docker.com/_/debian):
RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/* \
	&& localedef -i ${LOCALE_PLAIN} -c -f UTF-8 -A /usr/share/locale/locale.alias ${LOCALE}



# libpq-dev: needed for postgres access
# netcat-openbsd (netcat on ubuntu): for waiting for postgres to be started
RUN apt-get update && \
    apt-get install -y libxml2-dev libxslt1-dev  \
    libpq-dev  \
    cron  \
    netcat-openbsd  \
    sudo \
    subversion git  \
    unzip \
    && rm -rf /var/lib/apt/lists/*


# ADD UNIX USERS
################

# create group praktomat
RUN groupadd -g ${GROUP_ID} praktomat && \
  groupadd -g ${DOCKER_GROUP_ID} docker && \
# add user praktomat to group praktomat \
  useradd -g ${GROUP_ID} -u ${PRAKTOMAT_ID} praktomat -s /bin/sh --home /praktomat --create-home --comment "Praktomat Demon" && \
# add user praktomat to docker group \
  usermod -a -G ${DOCKER_GROUP_ID} praktomat && \
# add user praktomat to sudo (???) \
  usermod -aG sudo praktomat && \
  echo "praktomat:$PASSWORD" | sudo chpasswd

# allow user praktomat to start cron
RUN echo "praktomat ALL=NOPASSWD:SETENV: /usr/sbin/cron,/usr/local/bin/pyclean,/usr/local/bin/python3,/usr/bin/mount " >> /etc/sudoers && \
echo "praktomat ALL=(tester) NOPASSWD: ALL" >> /etc/sudoers


# RUN mkdir /praktomat && chown ${PRAKTOMAT_ID}:${GROUP_ID} /praktomat
WORKDIR /praktomat
ADD --chown=${PRAKTOMAT_ID}:${GROUP_ID} requirements.txt /praktomat/
RUN pip3 install --upgrade pip && \
    pip3 --version && \
    pip3 install -r requirements.txt --ignore-installed --force-reinstall --upgrade --no-cache-dir

COPY . /praktomat

RUN mkdir -p /praktomat/upload && mkdir -p /praktomat/media

# create cron job for deleting temporary files (no dots in new filename)
COPY cron.conf /etc/cron.d/praktomat-cron
RUN chmod 0644 /etc/cron.d/praktomat-cron \
  # Apply cron job
    && crontab /etc/cron.d/praktomat-cron

#COPY --chown=999:999 cron.conf /etc/cron.d/praktomat-cron
#RUN chmod 0644 /etc/cron.d/praktomat-cron


# set permissions
RUN chown praktomat:praktomat /praktomat/init_database.sh /praktomat/entrypoint.sh \
    && chmod u+x /praktomat/init_database.sh /praktomat/entrypoint.sh

# change user
USER praktomat

# run entrypoint.sh as user praktomat
ENTRYPOINT ["/praktomat/entrypoint.sh"]


