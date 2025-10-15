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

# Default
IMAGE=ubuntu-gnome-nomachine:22.04
CONTAINER=test-1
NomachineBindPort=2500
SshBindPort=2400
WorkSpaceBind=./workspace
CreateUserAccount=user
RenderType=Gpu
NvidiaDriver=Tesla
NVIDIA_VISIBLE_DEVICES=0

docker stop $CONTAINER || true
docker rm $CONTAINER || true

# Launch container as root to init core Linux services and
# launch the Display Manager and greeter. Switches to
# unprivileged user after login.
# --device=/dev/tty0 makes session creation cleaner.
# --ipc=host is set to allow Xephyr to use SHM XImages
docker run -d \
    -p $NomachineBindPort:4000 \
    -p $SshBindPort:22 \
    -p 4443:4443 \
    --privileged=true \
    --userns host \
    --device=/dev/tty0 \
    --name $CONTAINER \
    --ipc=host \
    --shm-size 2g \
    --security-opt apparmor=unconfined \
    --cap-add=SYS_ADMIN --cap-add=SYS_BOOT \
    --cgroupns=host \
    -v $WorkSpaceBind:/home/chen9619/InfantAgent/workspace \
    -e CreateUserAccount=$CreateUserAccount \
    -e RenderType=$RenderType \
    -e NvidiaDriver=$NvidiaDriver \
    -e NVIDIA_VISIBLE_DEVICES=$NVIDIA_VISIBLE_DEVICES \
    -e DISPLAY=:0 \
    $IMAGE /sbin/init

# docker run --name xgl -it -d --gpus 1 --tmpfs /dev/shm:rw -e TZ=UTC -e DISPLAY_SIZEW=1920 -e DISPLAY_SIZEH=1080 -e DISPLAY_REFRESH=60 -e DISPLAY_DPI=96 -e DISPLAY_CDEPTH=24 -e PASSWD=mypasswd -e SELKIES_ENCODER=nvh264enc -e SELKIES_VIDEO_BITRATE=8000 -e SELKIES_FRAMERATE=60 -e SELKIES_AUDIO_BITRATE=128000 -e SELKIES_BASIC_AUTH_PASSWORD=mypasswd -p 8080:8080 ghcr.io/selkies-project/nvidia-glx-desktop:latest


echo "Docker container started successfully"

# echo "Starting automatic GPU driver installation and virtual display configuration..."
# Start installation and configuration
# echo [ $NvidiaDriver == "Tesla" ]
# # sleep 5
if [ $NvidiaDriver == "Tesla" ]
then
    docker exec -it $CONTAINER chmod +x /home/Tesla-XorgDisplaySettingAuto.sh
    docker exec -it $CONTAINER /home/Tesla-XorgDisplaySettingAuto.sh
elif [ $NvidiaDriver == "GeForce" ]
then
    # Updated script for GeForce series GPUs
    # docker exec -it $CONTAINER curl -o GeForce-XorgDisplaySettingAuto_DP.sh https://raw.githubusercontent.com/ColorfulSS/docker-ubuntu-gnome-nomachine/master/2-remote-virtual-desktops/nx/ubuntu-18.04-gnome-nomachine/GeForce-XorgDisplaySettingAuto.sh
    # docker exec -it $CONTAINER chmod +x /home/GeForce-XorgDisplaySettingAuto_DP.sh
    # docker exec -it $CONTAINER /home/GeForce-XorgDisplaySettingAuto_DP.sh
    docker exec -it $CONTAINER /home/GeForce-XorgDisplaySettingAuto.sh
else
    echo "The current GPU type is not supported by the automatic script - please manually modify the script for installation and configuration"
fi

