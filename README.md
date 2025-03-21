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
cd computer
docker build -t ubuntu-gnome-nomachine:22.04 -f Dockerfile .
```

3. Run
```
export OPENAI_API_KEY='Your LLM API Key'
python infant/main.py
```

## Demo

[A simple demo](https://github.com/user-attachments/assets/6c127ecb-b55e-44c6-b696-65d63a1c377c)

## TODO

- [ ] Add: Credits.md.
- [ ] Add: Add RL training code.
- [x] Add: Add more web-browser tool.
- [x] FIX: web-browser tool related prompts.
- [x] FIX: check web-browser intermediate prompts.
- [ ] Add: Add more shots
- [ ] FIX: Polish Code
- [ ] Add waiting for user input state.
- [ ] Add: More emoj/user friendly front end.
- [ ] Add: evaluation in swe-bench/osworld/GAIA/GPQA...


