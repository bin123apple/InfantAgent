# Dockerfile for InfantAgent Server
# Build from project root: docker build -t infant-agent:latest -f Dockerfile .
FROM python:3.11-slim-bookworm

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies including OpenCV requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Download and install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# Create working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN uv venv && \
    uv pip install -e .

# Copy application code
COPY infant ./infant
COPY config.toml ./

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Create necessary directories
RUN mkdir -p /tmp/cache /tmp/file_store /app/workspace && \
    chmod 777 /tmp/cache /tmp/file_store /app/workspace

# Run the CLI application
CMD ["python", "-m", "infant"]
    