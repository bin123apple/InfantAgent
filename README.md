# InfantAgent

## Introduction
1. To build a multimodal agent that can interact with its own PC in a multimodal manner. This means it can autonomously operate the mouse and click anywhere on the screen, rather than relying solely on browser analysis to make decisions.

2. This agent system will be used for subsequent reinforcement learning training of agents.


## Setup 

NOTE: Now, it is only tested on linux server. There may be some bugs for Mac/Windows

1. Setup enviroment
```
cd InfantAgent
conda create --name infant python=3.11
conda activate infant
pip install poetry==1.7.1
poetry install
```

2. Build Docker 
```
cd sandbox
docker build -t ubuntu-gnome-nomachine:22.04 -f Dockerfile .
```

3. Run
```
export OPENAI_API_KEY='Your LLM API Key'
python infant/main.py
```

## Demo

Need a Demo here

## TODO

- [x] BUG: Sometimes the VM is laggy, it will hinder the normal process.
- [ ] BUG: Open_application() command waiting time too long
- [ ] Add: A demo.
- [ ] Add waiting for user input state.
- [ ] Add: Credits.md
- [ ] BUG: Move the localization function to here
- [ ] Add: evaluation in swe-bench/osworld/GAIA/GPQA...
- [ ] Add: More emoj/user friendly front end.


