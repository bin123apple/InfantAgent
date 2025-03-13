#!/bin/bash
# Run the Python script with the specified interpreter
export JUPYTER_PWD=$(pwd)
$INFANT_PYTHON_INTERPRETER /infant/tools/code_execute/execute_cli.py
