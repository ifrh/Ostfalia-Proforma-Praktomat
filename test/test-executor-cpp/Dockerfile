FROM python:3.11.9-slim-bookworm

# create user with less capabilties 
RUN useradd praktomat -s /bin/bash
#RUN useradd praktomat -s /bin/bash -g docker

# RUN sudo gpasswd -a $USER docker

# create sandbox folder and copy task and framework files into it, make writable
# WORKDIR 
# RUN chmod -R 777 
# ADD requirements.txt .

# install requirements
# RUN pip3 install --upgrade pip && pip3 install -r requirements.txt
RUN pip3 install --upgrade pip \
    && pip3 install docker

ADD executor.py .

# change user
# USER praktomat    

# *Docker-Gruppe**: Stellen Sie sicher, dass der Benutzer, unter dem Ihr Docker-Container läuft, 
# Mitglied der `docker`-Gruppe auf dem Host-System ist. 
# Sie können einem Benutzer mit dem Befehl `sudo usermod -aG docker your-username` zur Docker-Gruppe hinzufügen. 
# Danach müssen Sie sich ab- und wieder anmelden, damit die Gruppenänderung wirksam wird.

RUN ls -al
# run entrypoint.sh as user praktomat
# ENTRYPOINT ["python3 ./executor.py"]