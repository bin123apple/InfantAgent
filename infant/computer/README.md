# Quick Start

docker build -t ubuntu-gnome-nomachine:22.04 -f Dockerfile .

./run_docker.sh

check https://localhost:4443/

# Current Bug

If use ubuntu-22.04, the passward will become invalid even if the passward is correct. 
However it will be good if we use the ubuntu-18.04

