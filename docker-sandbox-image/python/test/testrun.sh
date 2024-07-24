#!/bin/bash

# requires a virtual python environment
# - python3 -m venv venv
# - source venv/bin/activate
# - pip install xmlrunner unittest-xml-reporting (lxml)
# - pip list

date
# ls -al 

# ls -al ./..

# ls -al /solution

echo "Copy everything into sandbox"
mkdir -p sandbox
cp -r solution/* sandbox
cp -r task/* sandbox
cp -r ../framework/* sandbox

echo "Run tests"

# change directory (otherwise all python files get removed in task and solution folder)
cd sandbox && python3 run_suite.py
cd ..

echo "show result folder"

pwd

ls -al sandbox/__result__

date