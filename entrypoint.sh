#!/bin/sh
set -e

echo "Docker entrypoint"
#set -x


if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for PostgreSQL..."
    while ! nc -z $DB_HOST $DB_PORT; do sleep 1; done;
    echo "PostgreSQL started"
fi

echo "Cleaning docker and precreate docker images"
python3 /praktomat/src/proforma/sandbox.py



echo "starting cron"
sudo -n cron -f &
# sudo -n /usr/sbin/cron -f &

#python manage.py flush --no-input
#python manage.py migrate
#python manage.py collectstatic --no-input

# create database tables
/praktomat/init_database.sh

cd /praktomat/src

exec "$@"
