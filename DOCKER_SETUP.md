# Docker Setup Guide for InfantAgent

This guide explains how to run InfantAgent using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+ with Docker Compose V2
- NVIDIA Docker runtime (nvidia-docker2)
- NVIDIA GPU with CUDA support
- At least 16GB RAM
- 50GB free disk space

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/bin123apple/InfantAgent.git
cd InfantAgent
```

### 2. Set Environment Variables

Create a `.env` file in the project root:

```bash
# Required: Your Anthropic API key
ANTHROPIC_API_KEY=your_api_key_here

# Optional: Specify which GPUs to use (default: 0,1)
CUDA_VISIBLE_DEVICES=0,1
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
- **Guacamole Desktop**: http://localhost:4443/guacamole/#/client/GNOME
  - Username: `web`
  - Password: `web`
  - Desktop credentials: `infant` / `123`

## Architecture

The Docker Compose setup includes two main services:

### 1. infant-agent (Main Server)
- Runs the FastAPI backend server
- Handles agent logic and LLM interactions
- Uses NVIDIA GPU for model inference
- Exposed on port 8000

### 2. computer-container (Desktop Environment)
- Ubuntu 22.04 with GNOME desktop
- Accessible via Guacamole web interface
- SSH access on port 22222
- Shared workspace with agent server

## Configuration

### GPU Configuration

By default, the setup uses 2 GPUs:
- GPU 0,1: Used by the InfantAgent server for model inference
- GPU 0: Used by the computer container for display rendering

To modify GPU allocation, edit `docker-compose.yaml`:

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0,1  # Change GPU IDs here
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
docker-compose logs -f computer-container

# Restart a specific service
docker-compose restart infant-agent

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

### Development Mode

Mount source code for live reloading:

```yaml
infant-agent:
  volumes:
    - ./infant:/app/infant
    - ./backend.py:/app/backend.py
  command: uvicorn backend:app --reload --host 0.0.0.0 --port 8000
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
