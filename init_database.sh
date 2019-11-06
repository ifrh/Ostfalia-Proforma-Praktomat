#!/bin/bash
DATABASE_INITIALISED=0

echo "create database"

if [ -e "$HOME/.DATABASE_INITIALISED" ];  then
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
py3clean .

# update tables in case of a modified or added checker
echo "migrate schema"
# do not use exit here!
python3 ./src/manage-docker.py makemigrations --noinput

# use initial in order to create initial migrations file
#python ./src/manage.py schemamigration checker --initial
echo "migrate checker"
python3 ./src/manage-docker.py migrate || exit

echo "create users"
echo "from django.contrib.auth.models import User; User.objects.create_superuser('$SUPERUSER', '$EMAIL', '$PASSWORD')" | python3 ./src/manage-docker.py shell
echo "from django.contrib.auth.models import User; User.objects.create_user('sys_prod', '$EMAIL', '$PASSWORD')" | python3 ./src/manage-docker.py shell

# update media folder for nginx to serve static django files
echo "collect static files for webserver"
python3 ./src/manage-docker.py collectstatic -i tiny_mce -i django_tinymce  -i django_extensions  --noinput || exit
#save it output the file
echo $DATABASE_INITIALISED > "$HOME/.DATABASE_INITIALISED"
echo "Database has been initialised successfully"  




