# InfantAgent

## Introduction
1. To build a multimodal agent that can interact with its own PC in a multimodal manner. This means it can autonomously operate the mouse and click anywhere on the screen, rather than relying solely on browser analysis to make decisions.

2. This agent system will be used for subsequent reinforcement learning training of agents.

## Installation Requirements

NOTE: Now, it is only tested on `linux` server with `Nvidia Tesla GPU (A100, H200 ...)`. There may be some bugs for Mac/Windows.

## Setup 

1. Setup enviroment
```
cd InfantAgent
conda create --name infant python=3.11
conda activate infant
conda install -c conda-forge uv
uv pip install -e .
```

2. Pull the Docker. Only required on the first use. It will pull the docker image from the Docker Hub.
```
docker pull bin12345/ubuntu-gnome-nomachine:22.04
```

3. (Optional) Config the config.toml file. If `Claude-3.7-Sonnet` is the default model.

4. Run
```
export ANTHROPIC_API_KEY='Your LLM API Key'
python infant/main.py
```

## Demo

[A simple demo](https://github.com/user-attachments/assets/6c127ecb-b55e-44c6-b696-65d63a1c377c)

## TODO

- [ ] Add: Credits.md.
- [ ] Add: Add RL training code.
- [ ] Add: Add more shots
- [ ] FIX: Polish Code
- [ ] Add: More emoj/user friendly front end.
- [ ] Add: evaluation in swe-bench/osworld/GAIA/GPQA...


