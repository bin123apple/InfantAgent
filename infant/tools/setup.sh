#!/bin/bash

set -e

export PATH=/infant/miniforge3/bin:$PATH
# Hardcoded to use the Python interpreter from the Infant runtime client
INFANT_PYTHON_INTERPRETER=/infant/miniforge3/bin/python
# check if INFANT_PYTHON_INTERPRETER exists and it is usable
if [ -z "$INFANT_PYTHON_INTERPRETER" ] ||  [ ! -x "$INFANT_PYTHON_INTERPRETER" ]; then
    echo "INFANT_PYTHON_INTERPRETER is not usable. Please pull the latest Docker image!"
    exit 1
fi

# Install dependencies
$INFANT_PYTHON_INTERPRETER -m pip install jupyterlab notebook jupyter_kernel_gateway

# add agent_skills to PATH
echo 'export PATH=/:$PATH' >> ~/.bashrc
echo 'export PATH=/infant:$PATH' >> ~/.bashrc
echo 'export PATH=/infant/tools:$PATH' >> ~/.bashrc
echo 'export PATH=/infant/tools/computer_use:$PATH' >> ~/.bashrc
echo 'export PATH=/infant/tools/file_editor:$PATH' >> ~/.bashrc
echo 'export PATH=/infant/tools/file_reader:$PATH' >> ~/.bashrc
echo 'export PATH=/infant/tools/file_searcher:$PATH' >> ~/.bashrc
echo 'export PATH=/infant/tools/web_browser:$PATH' >> ~/.bashrc

# add agent_skills to PYTHONPATH
echo 'export PYTHONPATH=/:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant/tools:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant/tools/computer_use:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant/tools/file_editor:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant/tools/file_reader:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant/tools/file_searcher:$PYTHONPATH' >> ~/.bashrc
echo 'export PYTHONPATH=/infant/tools/web_browser:$PYTHONPATH' >> ~/.bashrc

source ~/.bashrc

# ADD /infant/tools to PATH to make `jupyter_cli` available
echo 'export PATH=$PATH:/infant/tools/code_execute' >> ~/.bashrc
echo 'export DISPLAY=:0' >> ~/.bashrc
export PATH=/infant/tools/code_execute:$PATH

# if user name is `infant`, add '/home/infant/.local/bin' to PATH
if [ "$USER" = "infant" ]; then
    echo 'export PATH=$PATH:/home/infant/.local/bin' >> ~/.bashrc
    echo "export INFANT_PYTHON_INTERPRETER=$INFANT_PYTHON_INTERPRETER" >> ~/.bashrc
    export PATH=$PATH:/home/infant/.local/bin
    export PIP_CACHE_DIR=$HOME/.cache/pip
fi
# if user name is `root`, add '/root/.local/bin' to PATH
if [ "$USER" = "root" ]; then
    echo 'export PATH=$PATH:/root/.local/bin' >> ~/.bashrc
    echo "export INFANT_PYTHON_INTERPRETER=$INFANT_PYTHON_INTERPRETER" >> ~/.bashrc
    export PATH=$PATH:/root/.local/bin
    export PIP_CACHE_DIR=$HOME/.cache/pip
fi

# Run background process to start jupyter kernel gateway
# write a bash function that finds a free port
find_free_port() {
  local start_port="${1:-20000}"
  local end_port="${2:-65535}"

  for port in $(seq $start_port $end_port); do
    if ! ss -tuln | awk '{print $5}' | grep -q ":$port$"; then
      echo $port
      return
    fi
  done

  echo "No free ports found in the range $start_port to $end_port" >&2
  return 1
}

export JUPYTER_GATEWAY_PORT=$(find_free_port 20000 30000)
echo "JUPYTER_GATEWAY_PORT: $JUPYTER_GATEWAY_PORT"
$INFANT_PYTHON_INTERPRETER -m \
  jupyter kernelgateway --KernelGatewayApp.ip=0.0.0.0 --KernelGatewayApp.port=$JUPYTER_GATEWAY_PORT > /infant/logs/jupyter_kernel_gateway.log 2>&1 &

export JUPYTER_GATEWAY_PID=$!
echo "export JUPYTER_GATEWAY_PID=$JUPYTER_GATEWAY_PID" >> ~/.bashrc
export JUPYTER_GATEWAY_KERNEL_ID="default"
echo "export JUPYTER_GATEWAY_KERNEL_ID=$JUPYTER_GATEWAY_KERNEL_ID" >> ~/.bashrc
echo "JupyterKernelGateway started with PID: $JUPYTER_GATEWAY_PID"

# Start the jupyter_server
export JUPYTER_EXEC_SERVER_PORT=$(find_free_port 30000 40000)
echo "JUPYTER_EXEC_SERVER_PORT: $JUPYTER_EXEC_SERVER_PORT"
echo "export JUPYTER_EXEC_SERVER_PORT=$JUPYTER_EXEC_SERVER_PORT" >> ~/.bashrc
$INFANT_PYTHON_INTERPRETER /infant/tools/code_execute/execute_server.py > /infant/logs/jupyter_execute_server.log 2>&1 &
export JUPYTER_EXEC_SERVER_PID=$!
echo "export JUPYTER_EXEC_SERVER_PID=$JUPYTER_EXEC_SERVER_PID" >> ~/.bashrc
echo "Execution server started with PID: $JUPYTER_EXEC_SERVER_PID"

# Wait until /infant/logs/jupyter_kernel_gateway.log contains "is available"
while ! grep -q "at" /infant/logs/jupyter_kernel_gateway.log; do
    echo "Waiting for Jupyter kernel gateway to be available..."
    sleep 1
done
# Wait until /infant/logs/jupyter_execute_server.log contains "Jupyter kernel created for conversation"
while ! grep -q "kernel created" /infant/logs/jupyter_execute_server.log; do
    echo "Waiting for Jupyter kernel to be created..."
    sleep 1
done
echo "Jupyter kernel ready."
echo "JUPYTER_GATEWAY_PORT: $JUPYTER_GATEWAY_PORT"
echo "JUPYTER_EXEC_SERVER_PORT: $JUPYTER_EXEC_SERVER_PORT"

source ~/.bashrc

$INFANT_PYTHON_INTERPRETER -m pip install flake8 python-docx pypdf python-pptx pylatexenc openai opencv-python chardet pandas