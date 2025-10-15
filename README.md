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

## Recent Updates

We’ve switched from NoMachine to the open-source Guacamole for desktop sharing, because NoMachine requires a license for multi-user concurrent sessions. The Docker code has just been updated to support this change, and we will roll out a few follow-up patches to address remaining edge cases and polish the experience.

## Installation Requirements

Now, it is only tested on `linux` server with `Nvidia Tesla GPU (A100, H200 ...)`. The GPU is for open-spurce model inference. There may be some bugs for Mac/Windows.

## Setup

### Option 1: Docker Compose Setup (Recommended)

This is the recommended approach for running InfantAgent as a complete containerized system with all services.

1. **Prerequisites**
   - Docker and Docker Compose installed
   - NVIDIA GPU with drivers installed (for vLLM inference)
   - NVIDIA Container Toolkit installed

2. **Configure Environment Variables**

   Create a `.env` file in the project root:
   ```bash
   cd InfantAgent
   cp .env.example .env
   ```

   Edit `.env` and add your API keys:
   ```bash
   # Required: Claude API key for the agent
   ANTHROPIC_API_KEY=your_anthropic_api_key_here

   # Optional: Hugging Face token for downloading models
   HF_API_KEY=your_huggingface_token_here

   # Optional: Custom port configuration
   SSH_PORT=63710
   GUI_PORT=4443
   ```

3. **Build and Start All Services**
   ```bash
   # Build all containers (first time only)
   docker compose build

   # Start all services in background
   docker compose up -d

   # View logs
   docker compose logs -f

   # View agent logs specifically
   docker compose logs -f infant-agent-cli
   ```

4. **Access the Services**
   - **Guacamole Web Desktop**: http://localhost:4443/guacamole/
     - Login: `web` / `web`
     - Connection: Click "GNOME Desktop (RDP)"
   - **SSH to Computer Container**: `ssh infant@localhost -p 63710` (password: `123`)
   - **RDP Direct Access**: `localhost:3389` (username: `infant`, password: `123`)
   - **vLLM Server**: http://localhost:8005 (for OSS model inference)

5. **Managing Containers**
   ```bash
   # Stop all services
   docker compose down

   # Restart specific service
   docker compose restart infant-agent-cli

   # Rebuild after code changes
   docker compose down
   docker compose build infant-agent
   docker compose up -d

   # View running containers
   docker compose ps

   # Execute commands in agent container
   docker exec -it infant-agent-cli bash
   ```

6. **Interacting with the Agent**

   The agent is ready to receive prompts once you see the log:
   ```
   INFO: Current working directory: /workspace
   ```

   You can interact with the agent using the provided CLI tools:
   ```bash
   # Send a single prompt
   python3 send_prompt.py "Create a Python script to analyze data.csv"

   # Interactive mode
   python3 send_prompt.py --interactive

   # View agent logs
   python3 send_prompt.py --logs

   # Using bash script
   ./agent_cli.sh send "Your task here"
   ./agent_cli.sh logs -f
   ./agent_cli.sh status
   ```

7. **Troubleshooting**
   ```bash
   # Check service health
   docker compose ps

   # View detailed logs
   docker compose logs infant-computer
   docker compose logs vllm-server

   # Restart unhealthy services
   docker compose restart

   # Clean up and rebuild
   docker compose down -v  # Remove volumes
   docker compose build --no-cache
   docker compose up -d
   ```

### Option 2: Manual Setup (Advanced)

1. Setup environment
```
cd InfantAgent
conda create --name infant python=3.11
conda activate infant
conda install -c conda-forge uv
uv pip install -e .
```

2. Build the Docker. Only required on the first use. It will pull the docker image from the Docker Hub.
```
cd InfantAgent/infant/computer
docker build -t ubuntu-gnome-nomachine:latest -f Dockerfile .
```

3. Run
```
export CUDA_VISIBLE_DEVICES=0,1 # For Visual Grounding model inference
uvicorn backend:app --log-level info
```

4. Configure Virtual Machine (You only need to configure it once when using it for the first time.)

- Enter your api key in `setting`
By default, you should enter the Claude API key. You can also change this in the `config.py` file.

- Wait for the backend to configure automatically until you see the following instruction:
`For first-time users, please go to http://localhost:4443/guacamole/#/client/GNOME to set up and skip unnecessary steps.`

- Go to http://localhost:4443/guacamole/#/client/GNOME
Skip the security check (this is HTTPS, not HTTP), and you will see the Linux desktop.

- Go back to terminal and press `enter` to skip this reminder:
`When the computer setup is complete, press Enter to continue`

- Go back to the frontend and **refresh the page**.
In the upper-right corner of the virtual machine, enter your username and password. By default, the username for the guacamole is `web` and the password is also `web`. The computer username is `infant` and the password is `123`. You can also change these in the `config.py` file.

Now the agent is ready to use, and you don't need to configure the virtual machine again as long as the container still exists.

## Demo

[A simple demo](https://github.com/user-attachments/assets/6c127ecb-b55e-44c6-b696-65d63a1c377c)

## A simple web application demo

![A simple web application demo](https://github.com/bin123apple/InfantAgent/blob/main/asset/simple_web_application.png)


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




