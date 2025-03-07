#!/bin/bash
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# Image Name IMAGE
read -p "Please enter the image name to use (e.g., colorfulsky/ubuntu-gnome-nomachine:18.04): " IMAGE
while test -z "$IMAGE"
do
    read -p "Input is empty, please enter again: " IMAGE
done

# Container Name CONTAINER
read -p "Please set the container name (e.g., ubuntu-gnome-nomachine-1): " CONTAINER
while test -z "$CONTAINER"
do
    read -p "Input is empty, please enter again: " CONTAINER
done

# Nomachine Mapped Port NomachineBindPort
read -p "Please set the Nomachine mapped port (e.g., 23333): " NomachineBindPort
while test -z "$NomachineBindPort"
do
    read -p "Input is empty, please enter again: " NomachineBindPort
done

# SSH Mapped Port SshBindPort
read -p "Please set the SSH mapped port (e.g., 22222): " SshBindPort
while test -z "$SshBindPort"
do
    read -p "Input is empty, please enter again: " SshBindPort
done

# Workspace Mapped Directory WorkSpaceBind
read -p "Please set the directory mapping (e.g., /data/workspace/xxx): " WorkSpaceBind
while test -z "$WorkSpaceBind"
do
    read -p "Input is empty, please enter again: " WorkSpaceBind
done

# Create Username CreateUserAccount
read -p "Please set the login username (e.g., user): " CreateUserAccount
while test -z "$CreateUserAccount"
do
    read -p "Input is empty, please enter again: " CreateUserAccount
done

# Renderer Type RenderType
echo "====== CPU rendering is faster; choose GPU for special needs ======"
read -p "Please select the renderer type (e.g., Gpu / Cpu): " RenderType
while test -z "$RenderType"
do
    read -p "Input is empty, please enter again: " RenderType
done

# Select GPU for Rendering
echo "====== Select GPU for rendering ======"
read -p "Please select the GPU number (e.g., 0 or 1 2 3 ...): " NVIDIA_VISIBLE_DEVICES
while test -z "$NVIDIA_VISIBLE_DEVICES"
do
    read -p "Input is empty, please enter again: " NVIDIA_VISIBLE_DEVICES
done

# Automatic Installation of GPU Drivers
# Determine GPU type and install the corresponding driver
echo "Tesla series: V100 A100 ... | GeForce series: 3090 2080 ..."
read -p "Please confirm the GPU series [e.g., enter Tesla for V100 / enter GeForce for RTX3090]: " NvidiaDriver
while test -z "$NvidiaDriver"
do
    read -p "Input is empty, please enter again: " NvidiaDriver
done

# Default
# IMAGE=ubuntu-gnome-nomachine:18.04
# CONTAINER=ubuntu-nomachine-testmod
# NomachineBindPort=25009
# SshBindPort=24002
# WorkSpaceBind=/data/workspace/youguoliang
# CreateUserAccount=colorful

# Launch container as root to init core Linux services and
# launch the Display Manager and greeter. Switches to
# unprivileged user after login.
# --device=/dev/tty0 makes session creation cleaner.
# --ipc=host is set to allow Xephyr to use SHM XImages
docker run -d \
    --restart=always \
    -p $NomachineBindPort:4000 \
    -p $SshBindPort:22 \
    -p 4443:4443 \
    --privileged=true\
    --userns host \
    --device=/dev/tty0 \
    --name $CONTAINER \
    --ipc=host \
    --shm-size 2g \
    --security-opt apparmor=unconfined \
    --cap-add=SYS_ADMIN --cap-add=SYS_BOOT \
    -e CreateUserAccount=$CreateUserAccount \
    -e RenderType=$RenderType \
    -e NvidiaDriver=$NvidiaDriver \
    -e NVIDIA_VISIBLE_DEVICES=$NVIDIA_VISIBLE_DEVICES \
    -e DISPLAY=:0 \
    -v /sys/fs/cgroup:/sys/fs/cgroup \
    -v $WorkSpaceBind:/data \
    $IMAGE /sbin/init

echo "Docker container started successfully"

echo "Starting automatic GPU driver installation and virtual display configuration..."
# Start installation and configuration
echo [ $NvidiaDriver == "Tesla" ]
if [ $NvidiaDriver == "Tesla" ]
then
    docker exec -it $CONTAINER /home/Tesla-XorgDisplaySettingAuto.sh
elif [ $NvidiaDriver == "GeForce" ]
then
    # Updated script for GeForce series GPUs
    docker exec -it $CONTAINER curl -o GeForce-XorgDisplaySettingAuto_DP.sh https://raw.githubusercontent.com/ColorfulSS/docker-ubuntu-gnome-nomachine/master/2-remote-virtual-desktops/nx/ubuntu-18.04-gnome-nomachine/GeForce-XorgDisplaySettingAuto.sh
    docker exec -it $CONTAINER chmod +x /home/GeForce-XorgDisplaySettingAuto_DP.sh
    docker exec -it $CONTAINER /home/GeForce-XorgDisplaySettingAuto_DP.sh
    #docker exec -it $CONTAINER /home/GeForce-XorgDisplaySettingAuto.sh
else
    echo "The current GPU type is not supported by the automatic script - please manually modify the script for installation and configuration"
fi

