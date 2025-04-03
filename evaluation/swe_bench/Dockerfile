ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

RUN apt-get update && apt-get install -y \
    xdotool \
    curl \
    wget \
    git \
    vim \
    nano \
    unzip \
    zip \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    openssh-server \
    sudo \
    gcc \
    jq \
    g++ \
    make \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p -m0755 /var/run/sshd
RUN mkdir -p -m0755 /run/sshd

RUN mkdir -p /infant && mkdir -p /infant/logs && chmod 777 /infant/logs
RUN wget --progress=bar:force -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
RUN bash Miniforge3.sh -b -p /infant/miniforge3
RUN chmod -R g+w /infant/miniforge3
RUN bash -c ". /infant/miniforge3/etc/profile.d/conda.sh && conda config --set changeps1 False && conda config --append channels conda-forge"
RUN echo "" > /infant/bash.bashrc
RUN rm -f Miniforge3.sh

# RUN ln -sf /opt/miniconda3/envs/testbed/bin/python /infant/miniforge3/bin/python

# - agentskills dependencies
RUN /infant/miniforge3/bin/pip install --upgrade pip
RUN /infant/miniforge3/bin/pip install jupyterlab notebook jupyter_kernel_gateway flake8 Pillow
RUN /infant/miniforge3/bin/pip install python-docx PyPDF2 python-pptx pylatexenc openai
RUN /infant/miniforge3/bin/pip install python-dotenv toml termcolor pydantic python-docx pyyaml docker pexpect tenacity e2b minio

