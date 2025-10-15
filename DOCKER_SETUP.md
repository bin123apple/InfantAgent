# Docker Setup Guide for InfantAgent

This guide explains how to run InfantAgent using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+ with Docker Compose V2
- NVIDIA Docker runtime (nvidia-docker2) - only required for GPU-accelerated components
- NVIDIA GPU with CUDA support (minimum 3 GPUs recommended for full setup)
  - 2 GPUs for vLLM server (UI-TARS model with tensor parallelism)
  - 1 GPU for computer container (display rendering)
  - InfantAgent server runs on CPU (no GPU needed)
  - Can work with fewer GPUs by adjusting configuration
- At least 32GB RAM (64GB recommended)
- 100GB free disk space (for model downloads and workspace)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/bin123apple/InfantAgent.git
cd InfantAgent
```

### 2. Set Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env
```

Required variables:
```bash
# Required: Your Anthropic API key
ANTHROPIC_API_KEY=your_api_key_here

# Optional but recommended: Hugging Face token for UI-TARS model
HUGGING_FACE_HUB_TOKEN=your_huggingface_token_here

# Optional: Specify which GPUs to use (default: 0,1,2,3)
CUDA_VISIBLE_DEVICES=0,1,2,3
```

### 3. Build and Start Services

```bash
# Build both containers
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access the Services

- **InfantAgent API**: http://localhost:8000
- **vLLM Server API**: http://localhost:8001/v1 (OpenAI-compatible API)
- **Guacamole Desktop**: http://localhost:4443/guacamole/#/client/GNOME
  - Username: `web`
  - Password: `web`
  - Desktop credentials: `infant` / `123`

## Architecture

The Docker Compose setup includes three main services:

### 1. vllm-server (OSS Model Server)
- Hosts the UI-TARS-1.5-7B model using vLLM
- OpenAI-compatible API endpoint
- Tensor parallelism across 2 GPUs for faster inference
- Exposed on port 8001
- Automatic model download from Hugging Face

### 2. infant-agent (Main Server)
- Runs the FastAPI backend server
- Handles agent logic and orchestration
- Connects to vLLM server for OSS model inference
- Runs on CPU (no GPU required)
- Exposed on port 8000

### 3. computer-container (Desktop Environment)
- Ubuntu 22.04 with GNOME desktop
- Accessible via Guacamole web interface
- SSH access on port 22222
- Shared workspace with agent server

## Configuration

### GPU Configuration

By default, the setup uses 3 GPUs:
- **GPU 2,3**: vLLM server (UI-TARS-1.5-7B model with tensor parallelism)
- **GPU 0**: Computer container (display rendering)
- **InfantAgent server**: Runs on CPU (no GPU needed)

**For systems with fewer GPUs:**

If you only have 2 GPUs, modify `docker-compose.yaml`:

```yaml
# vLLM server - use single GPU
vllm-server:
  environment:
    - CUDA_VISIBLE_DEVICES=1
  command: >
    --model ByteDance-Seed/UI-TARS-1.5-7B
    --tensor-parallel-size 1  # Changed from 2
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['1']  # Single GPU

# Computer - use first GPU
computer-container:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']

# InfantAgent - no GPU needed (runs on CPU)
```

If you only have 1 GPU (vLLM only, no desktop GUI):
```yaml
# vLLM server - use the only GPU
vllm-server:
  environment:
    - CUDA_VISIBLE_DEVICES=0
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']

# Computer container - disable or run without GPU
computer-container:
  # Comment out the deploy.resources section to run without GPU
  # Or don't start it: docker-compose up -d vllm-server infant-agent
```

### Workspace Volumes

The `./workspace` directory is shared between:
- Host machine: `./workspace`
- Agent server: `/app/workspace`
- Computer container: `/workspace`

Files created in any location are accessible from all others.

### Config Updates

To update the configuration without rebuilding:

1. Edit `config.toml`
2. Restart the agent service:
   ```bash
   docker-compose restart infant-agent
   ```

## Common Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f infant-agent
docker-compose logs -f vllm-server
docker-compose logs -f computer-container

# Restart a specific service
docker-compose restart infant-agent

# Check vLLM server status and model loading progress
docker-compose logs -f vllm-server | grep -i "model\|loading\|ready"

# Rebuild after code changes
docker-compose build --no-cache infant-agent
docker-compose up -d

# Access agent container shell
docker exec -it infant-agent-server bash

# Access computer container shell
docker exec -it infant-computer bash

# Monitor resource usage
docker stats
```

## Troubleshooting

### GPU Not Detected

Verify NVIDIA Docker runtime is installed:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

If this fails, install nvidia-docker2:

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### Container Won't Start

Check logs for errors:

```bash
docker-compose logs computer-container
```

Common issues:
- Port conflicts: Change ports in `docker-compose.yaml`
- Insufficient memory: Increase Docker memory limit
- Missing GPU: Check `nvidia-smi` output

### Connection Refused to Guacamole

The computer container takes 1-2 minutes to fully initialize:

1. Check container status: `docker-compose ps`
2. Wait for health check to pass
3. Try accessing: http://localhost:4443/guacamole/

### vLLM Server Issues

**Model fails to download:**
- Check Hugging Face token is set: `echo $HUGGING_FACE_HUB_TOKEN`
- Verify internet connection
- Check disk space: `df -h`
- View download progress: `docker-compose logs -f vllm-server`

**Out of memory errors:**
- Reduce `--gpu-memory-utilization` from 0.9 to 0.7
- Use single GPU instead of tensor parallelism
- Reduce `--max-model-len` from 8192 to 4096

**vLLM server not responding:**
```bash
# Check if model is loaded
curl http://localhost:8001/v1/models

# Test inference
curl http://localhost:8001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ByteDance-Seed/UI-TARS-1.5-7B",
    "prompt": "Hello, how are you?",
    "max_tokens": 50
  }'
```

The vLLM server takes 2-5 minutes to download and load the model on first startup.

### Build Failures

Clear Docker cache and rebuild:

```bash
docker-compose down -v
docker system prune -a
docker-compose build --no-cache
docker-compose up -d
```

## Production Deployment

For production use, consider:

1. **Use docker-compose.prod.yaml** with:
   - Resource limits
   - Logging configuration
   - Secrets management
   - Network security

2. **Enable HTTPS** for Guacamole:
   - Use a reverse proxy (nginx/traefik)
   - Configure SSL certificates

3. **Persistent Storage**:
   - Use named volumes instead of bind mounts
   - Regular backup of workspace data

4. **Monitoring**:
   - Add Prometheus exporters
   - Configure health check endpoints
   - Set up alerting

## Advanced Configuration

### Custom Build Args

Build with custom Python version:

```bash
docker-compose build --build-arg PYTHON_VERSION=3.11 infant-agent
```

### Multi-GPU Setup

For systems with 4+ GPUs, distribute workload:

```yaml
infant-agent:
  environment:
    - CUDA_VISIBLE_DEVICES=0,1,2,3
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 4
            capabilities: [gpu]
```

### Using Different OSS Models

To use a different model with vLLM, modify the `docker-compose.yaml`:

```yaml
vllm-server:
  command: >
    --model meta-llama/Llama-3-8B  # Change model here
    --host 0.0.0.0
    --port 8000
    --tensor-parallel-size 1  # Adjust based on model size
    --max-model-len 4096
    --gpu-memory-utilization 0.9
    --trust-remote-code
```

Popular models:
- `meta-llama/Llama-3-8B`
- `mistralai/Mistral-7B-v0.1`
- `Qwen/Qwen2-7B`
- `ByteDance-Seed/UI-TARS-1.5-7B` (default, optimized for UI tasks)

### vLLM Performance Tuning

**For faster inference:**
```yaml
command: >
  --model ByteDance-Seed/UI-TARS-1.5-7B
  --enable-prefix-caching  # Cache common prefixes
  --enable-chunked-prefill  # Process long prompts efficiently
  --max-num-seqs 16  # Increase batch size
```

**For lower memory usage:**
```yaml
command: >
  --model ByteDance-Seed/UI-TARS-1.5-7B
  --gpu-memory-utilization 0.7  # Reduce from 0.9
  --max-model-len 4096  # Reduce from 8192
  --quantization awq  # Use quantization (if model supports)
```

### Development Mode

Mount source code for live reloading:

```yaml
infant-agent:
  volumes:
    - ./infant:/app/infant
    - ./backend.py:/app/backend.py
  command: uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

### Running Without vLLM (API-only mode)

If you want to use only commercial APIs (no OSS models):

```bash
# Start without vLLM server
docker-compose up -d computer-container infant-agent

# Or comment out vllm-server in docker-compose.yaml
```

Update `config.toml`:
```toml
use_oss_llm = false
```

## Maintenance

### Update to Latest Version

```bash
cd InfantAgent
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

### Clean Up Resources

```bash
# Remove stopped containers
docker-compose down

# Remove all data (including volumes)
docker-compose down -v

# Clean up unused Docker resources
docker system prune -a --volumes
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/bin123apple/InfantAgent/issues
- Discord: https://discord.gg/urxApEGcwV
- Documentation: https://github.com/bin123apple/InfantAgent

## License

This project is licensed under the MIT License. See LICENSE file for details.
