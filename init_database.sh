#!/bin/bash
#set -x

DATABASE_INITIALISED=0

echo "create database"
#echo "Database is $DATABASE: $DB_NAME"

if [ -e "/praktomat/.DATABASE_INITIALISED" ];  then
    echo "Database is already created"
    exit 0
#else
#    echo "Initialise Database"
fi

# echo "syncing database"
# OLD python3 ./src/manage-docker.py syncdb --noinput --migrate
# python3 ./src/manage-docker.py migrate --noinput
#if [ $? -ne 0 ]; then 
#    exit 1 
#fi

# clear python cache since there can be old files that confuse migrations
echo "clean python cache"
sudo -n /usr/bin/py3clean /praktomat

# py3clean does not delete cache files generated from source files that have been deleted since
find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete

# update tables in case of a modified or added checker

echo "make migrations"
# do not use exit here!
sudo -n -E /usr/bin/python3 ./src/manage-docker.py makemigrations configuration
sudo -n -E /usr/bin/python3 ./src/manage-docker.py makemigrations accounts
sudo -n -E /usr/bin/python3 ./src/manage-docker.py makemigrations tasks
sudo -n -E /usr/bin/python3 ./src/manage-docker.py makemigrations solutions
sudo -n -E /usr/bin/python3 ./src/manage-docker.py makemigrations checker
sudo -n -E /usr/bin/python3 ./src/manage-docker.py makemigrations

echo "migrate"
python3 ./src/manage-docker.py migrate || exit

echo "create users"
echo "from django.contrib.auth.models import User; User.objects.create_superuser('$SUPERUSER', '$EMAIL', '$PASSWORD')" | python3 ./src/manage-docker.py shell
echo "from django.contrib.auth.models import User; User.objects.create_user('sys_prod', '$EMAIL', '$PASSWORD')" | python3 ./src/manage-docker.py shell

# update media folder for nginx to serve static django files
echo "collect static files for webserver"
python3 ./src/manage-docker.py collectstatic -i tiny_mce -i django_tinymce  -i django_extensions  --noinput || exit
#save it output the file
echo $DATABASE_INITIALISED > "/praktomat/.DATABASE_INITIALISED"
echo "Database has been initialised successfully"  




