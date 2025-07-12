# FROM scratch as build
FROM alpine:3.22 as build


# set locale
# THIS DOES NOT CHANGE THE LOCALE OF THE JDK OUTPUT!
# ARG LOCALE_PLAIN=de_DE
# ARG LOCALE=${LOCALE_PLAIN}.UTF-8
# RUN apk add --no-cache --update musl musl-utils musl-locales tzdata
# ENV TZ=Europe/Berlin
# RUN cp /usr/share/zoneinfo/Europe/Berlin /etc/localtime \
#    && echo 'export LC_ALL=${LOCALE}' >> /etc/profile.d/locale.sh \
#    && sed -i 's|LANG=C.UTF-8|LANG=${LOCALE}|' /etc/profile.d/locale.sh


# Checkstyle
ADD https://github.com/checkstyle/checkstyle/releases/download/checkstyle-10.17.0/checkstyle-10.17.0-all.jar \
    https://github.com/checkstyle/checkstyle/releases/download/checkstyle-10.1/checkstyle-10.1-all.jar \
    https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.23/checkstyle-8.23-all.jar \
    https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.29/checkstyle-8.29-all.jar \
# destination
    /praktomat/lib/


# set permissions for folder and files in /praktomat
# RUN find /praktomat -type d -exec chmod 755 {} \; \
#  && find /praktomat -type f -exec chmod 644 {} \;




FROM alpine:3.22

ARG PRAKTOMAT_ID=1100
# add user praktomat
RUN adduser -u ${PRAKTOMAT_ID} praktomat --disabled-password
# RUN adduser -u ${PRAKTOMAT_ID} praktomat -s /bin/ash --disabled-password

COPY --from=build --chown=praktomat /praktomat /praktomat

# java is required for running Checkstyle
RUN apk add --no-cache openjdk21-jre

# create sandbox folder
WORKDIR /sandbox

RUN chmod -R 777 /sandbox

# change user
USER praktomat


