<div align="center">
<h1 align="center">
  <sub>
    <img
      src="https://raw.githubusercontent.com/bin123apple/InfantAgent/main/asset/Logo.png"
      alt="InfantAgent Logo"
      width="40"
    />
  </sub>
  InfantAgent: A multimodal agent that can interact with its own PC in a multimodal manner.
</h1>


<a href="https://discord.gg/urxApEGcwV">
  <img 
    src="https://img.shields.io/badge/Discord-Join%20Us-purple?logo=discord&logoColor=white&style=for-the-badge"
    alt="Join our Discord community"
  />
</a>

<a href="https://arxiv.org/abs/2505.10887">
  <img 
    src="https://img.shields.io/badge/arXiv-2505.10887-%23B31B1B?logo=arxiv&logoColor=white&style=for-the-badge" 
    alt="Read our paper on arXiv" 
  />
</a>
</div>

## Introduction
1. To build a multimodal agent that can interact with its own PC in a multimodal manner. This means it can autonomously operate the mouse and click anywhere on the screen, rather than relying solely on browser analysis to make decisions.

2. This agent system will be used for subsequent reinforcement learning training of agents.

3. I have not yet conducted large-scale testing of this agent beyond the benchmark; please feel free to report any bugs or submit pull requests. :wave:

## Installation Requirements

Now, it is only tested on `linux` server with `Nvidia Tesla GPU (A100, H200 ...)`. The GPU is for open-spurce model inference. There may be some bugs for Mac/Windows.

## Setup 

1. Setup environment
```
cd InfantAgent
conda create --name infant python=3.11
conda activate infant
conda install -c conda-forge uv
uv pip install -e .
```

2. Pull the Docker. Only required on the first use. It will pull the docker image from the Docker Hub.
```
docker pull winsonchen108/ubuntu-gnome-nomachine:latest
```

3. (Optional) Config the config.toml file. If `Claude-3.7-Sonnet` is the default model.

4. Run
```
export ANTHROPIC_API_KEY='Your LLM API Key'
python infant/main.py
```

NOTE: When you start the Docker container for the first time, it takes a bit of time to install the NVIDIA driver. As long as the container still exists, you won’t need to install it again on subsequent runs.

## Demo

[A simple demo](https://github.com/user-attachments/assets/6c127ecb-b55e-44c6-b696-65d63a1c377c)

## A simple web application demo

Finish Setup and Run:

```
uvicorn backend:app --log-level info
```

Choose your model & API Key in `setting`.

![A simple web application demo](https://github.com/bin123apple/InfantAgent/blob/main/asset/simple_web_application.png)

## TODO
- [ ] Add: More emoj/user friendly front end.

## Acknowledgements
Thanks to the many outstanding open-source projects and models.

1. [OpenHands](https://github.com/All-Hands-AI/OpenHands) Our Docker container’s configuration, connection setup, and Jupyter execution method are based on OpenHands, and we used the OpenHands testbed for SWE-Bench testing.

2. [browser-use](https://github.com/browser-use/browser-use) Our web-browser tools are modified from browser-use.

3. [docker-ubuntu-gnome-nomachine](https://github.com/ColorfulSS/docker-ubuntu-gnome-nomachine) We modified the code for this to setup the nomachine display.

4. [UI-TARS](https://github.com/bytedance/UI-TARS) We use UI-TARS-1.5 7B as our default visual-grounding model.


## Cite

```
@misc{lei2025infantagentnextmultimodalgeneralistagent,
      title={InfantAgent-Next: A Multimodal Generalist Agent for Automated Computer Interaction}, 
      author={Bin Lei and Weitai Kang and Zijian Zhang and Winson Chen and Xi Xie and Shan Zuo and Mimi Xie and Ali Payani and Mingyi Hong and Yan Yan and Caiwen Ding},
      year={2025},
      eprint={2505.10887},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2505.10887}, 
}
```




