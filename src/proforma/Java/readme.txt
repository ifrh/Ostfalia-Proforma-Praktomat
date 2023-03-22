# execute in container!!
docker exec -ti praktomat3 /bin/bash

# more permissions
sudo /bin/bash

# change cwd
cd src/proforma/Java

# compile
javac -cp ../../../lib/junit-4.12.jar:../../../lib/hamcrest-core-1.3.jar:. de/ostfalia/zell/praktomat/Junit4ProFormAListener.java

# create jar
# note: this jar does not run properly
jar -cvf ../../../extra/Junit4RunListener.jar  de/ostfalia/zell/praktomat/Junit4ProFormAListener.class de/ostfalia/zell/praktomat/TestDescription.class