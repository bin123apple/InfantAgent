#!/bin/bash

set -e

INFANT_PYTHON_INTERPRETER=/infant/miniforge3/bin/python
# check if INFANT_PYTHON_INTERPRETER exists and it is usable
if [ -z "$INFANT_PYTHON_INTERPRETER" ] ||  [ ! -x "$INFANT_PYTHON_INTERPRETER" ]; then
    echo "INFANT_PYTHON_INTERPRETER is not usable. Please pull the latest Docker image!"
    exit 1
fi

# add agent_skills to PATH
echo 'export PATH=/infant/plugins/agent_skills:$PATH' >> ~/.bashrc

# add agent_skills to PYTHONPATH
echo 'export PYTHONPATH=/infant/plugins/agent_skills:$PYTHONPATH' >> ~/.bashrc

source ~/.bashrc

$INFANT_PYTHON_INTERPRETER -m pip install flake8 python-docx pypdf python-pptx pylatexenc openai opencv-python chardet pandas
