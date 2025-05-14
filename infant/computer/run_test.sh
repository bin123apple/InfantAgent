IMAGE=ubuntu-gnome-nomachine:22.04
CONTAINER=test-1 # Make sure this container name is not already in use or remove it first
NomachineBindPort=2500
SshBindPort=2400
WorkSpaceBind=./workspace # Ensure this path is correct relative to where you run docker
CreateUserAccount=user
RenderType=Gpu
NvidiaDriver=Tesla # or GeForce, depending on your setup
NVIDIA_VISIBLE_DEVICES=0

# Stop and remove the old container if it exists
docker stop $CONTAINER || true
docker rm $CONTAINER || true

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
    -v /sys/fs/cgroup:/sys/fs/cgroup \
    -v $WorkSpaceBind:/home/chen9619/workspace \
    -e CreateUserAccount=$CreateUserAccount \
    -e RenderType=$RenderType \
    -e NvidiaDriver=$NvidiaDriver \
    -e NVIDIA_VISIBLE_DEVICES=$NVIDIA_VISIBLE_DEVICES \
    -e DISPLAY=:0 \
    $IMAGE /sbin/init # Overridden command to start a shell