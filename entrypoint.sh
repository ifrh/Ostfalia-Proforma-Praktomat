#!/bin/sh

echo "Docker entrypoint"


if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for PostgreSQL..."
    while ! nc -z $DB_HOST $DB_PORT; do sleep 1; done;
    echo "PostgreSQL started"
fi


echo start cron
cron -f &

#python manage.py flush --no-input
#python manage.py migrate
#python manage.py collectstatic --no-input

# create database tables
/praktomat/init_database.sh

cd /praktomat/src

exec "$@"
