# remove database build files 

# The migration can be build automatically on base of the source code. 

sudo rm -rf src/accounts/migrations
sudo rm -rf src/tasks/migrations
sudo rm -rf src/checker/migrations
sudo rm -rf src/solutions/migrations

# remove old files from Python cache

# sudo rm -rf __pycache__
sudo rm -rf *.pyc
