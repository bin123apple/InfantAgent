# vLLM Server Setup Guide

This guide focuses on the vLLM server component for hosting the UI-TARS-1.5-7B model.

## Quick Start

The vLLM server is automatically started when you run `docker-compose up -d`. It serves the UI-TARS-1.5-7B model via an OpenAI-compatible API.

## Configuration

### Default Settings

The vLLM server is configured in [docker-compose.yaml](docker-compose.yaml):

```yaml
vllm-server:
  image: vllm/vllm-openai:latest
  ports:
    - "8001:8000"
  environment:
    - CUDA_VISIBLE_DEVICES=2,3
  command: >
    --model ByteDance-Seed/UI-TARS-1.5-7B
    --tensor-parallel-size 2
    --max-model-len 8192
    --gpu-memory-utilization 0.9
```

### GPU Requirements

- **Minimum**: 1x GPU with 16GB VRAM
- **Recommended**: 2x GPUs with 24GB VRAM each (for tensor parallelism)
- **Model Size**: ~14GB (7B parameters)

### Environment Variables

Set in your `.env` file:

```bash
# Optional but recommended for faster downloads
HUGGING_FACE_HUB_TOKEN=your_token_here

# GPU allocation (adjust based on your system)
CUDA_VISIBLE_DEVICES=0,1,2,3
```

## Accessing the API

### Health Check

```bash
curl http://localhost:8001/health
```

### List Models

```bash
curl http://localhost:8001/v1/models
```

### Test Inference

```bash
curl http://localhost:8001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ByteDance-Seed/UI-TARS-1.5-7B",
    "prompt": "Click on the login button",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

### Chat Completions

```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ByteDance-Seed/UI-TARS-1.5-7B",
    "messages": [
      {"role": "user", "content": "What should I click to login?"}
    ],
    "max_tokens": 100
  }'
```

## Integration with InfantAgent

The InfantAgent server automatically connects to vLLM via the environment variable:

```yaml
infant-agent:
  environment:
    - VLLM_BASE_URL=http://vllm-server:8000/v1
```

In your `config.toml`, set:

```toml
use_oss_llm = true
base_url_oss = "http://vllm-server:8000/v1"
model_oss = "ByteDance-Seed/UI-TARS-1.5-7B"
```

## Performance Tuning

### For 2 GPUs (Recommended)

```yaml
vllm-server:
  environment:
    - CUDA_VISIBLE_DEVICES=2,3
  command: >
    --model ByteDance-Seed/UI-TARS-1.5-7B
    --tensor-parallel-size 2
    --max-model-len 8192
    --gpu-memory-utilization 0.9
    --disable-custom-all-reduce
```

### For 1 GPU (Minimum)

```yaml
vllm-server:
  environment:
    - CUDA_VISIBLE_DEVICES=1
  command: >
    --model ByteDance-Seed/UI-TARS-1.5-7B
    --tensor-parallel-size 1
    --max-model-len 4096
    --gpu-memory-utilization 0.85
```

### High Throughput Mode

```yaml
command: >
  --model ByteDance-Seed/UI-TARS-1.5-7B
  --tensor-parallel-size 2
  --max-model-len 8192
  --max-num-seqs 32
  --enable-prefix-caching
  --enable-chunked-prefill
```

### Low Memory Mode

```yaml
command: >
  --model ByteDance-Seed/UI-TARS-1.5-7B
  --tensor-parallel-size 1
  --max-model-len 2048
  --gpu-memory-utilization 0.7
  --max-num-seqs 8
```

## Using Alternative Models

### Llama 3 8B

```yaml
vllm-server:
  command: >
    --model meta-llama/Llama-3-8B
    --tensor-parallel-size 1
    --max-model-len 8192
```

### Mistral 7B

```yaml
vllm-server:
  command: >
    --model mistralai/Mistral-7B-v0.1
    --tensor-parallel-size 1
    --max-model-len 8192
```

### Qwen 2 7B

```yaml
vllm-server:
  command: >
    --model Qwen/Qwen2-7B
    --tensor-parallel-size 1
    --max-model-len 8192
    --trust-remote-code
```

## Monitoring

### View Logs

```bash
# All logs
docker-compose logs -f vllm-server

# Model loading progress
docker-compose logs -f vllm-server | grep -i "loading\|model\|ready"

# Errors only
docker-compose logs vllm-server | grep -i "error\|fail"
```

### Check GPU Usage

```bash
# From host
nvidia-smi

# From container
docker exec vllm-server nvidia-smi
```

### Monitor Performance

```bash
# Container stats
docker stats vllm-server

# Request latency
time curl http://localhost:8001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "ByteDance-Seed/UI-TARS-1.5-7B", "prompt": "test", "max_tokens": 10}'
```

## Troubleshooting

### Model Download Fails

**Issue**: Cannot download model from Hugging Face

**Solutions**:
1. Set Hugging Face token:
   ```bash
   export HUGGING_FACE_HUB_TOKEN=your_token_here
   docker-compose up -d vllm-server
   ```

2. Pre-download model:
   ```bash
   # On host machine
   huggingface-cli download ByteDance-Seed/UI-TARS-1.5-7B

   # Mount in docker-compose.yaml
   volumes:
     - ~/.cache/huggingface:/root/.cache/huggingface
   ```

### Out of Memory (OOM)

**Issue**: CUDA out of memory errors

**Solutions**:
1. Reduce memory utilization:
   ```yaml
   --gpu-memory-utilization 0.7  # Down from 0.9
   ```

2. Reduce context length:
   ```yaml
   --max-model-len 4096  # Down from 8192
   ```

3. Use single GPU:
   ```yaml
   --tensor-parallel-size 1  # Down from 2
   ```

4. Reduce batch size:
   ```yaml
   --max-num-seqs 4  # Smaller batch
   ```

### Slow Inference

**Issue**: Requests taking too long

**Solutions**:
1. Enable caching:
   ```yaml
   --enable-prefix-caching
   ```

2. Increase batch size:
   ```yaml
   --max-num-seqs 16
   ```

3. Use tensor parallelism (if you have 2+ GPUs):
   ```yaml
   --tensor-parallel-size 2
   ```

### Server Not Responding

**Issue**: Cannot connect to http://localhost:8001

**Check**:
```bash
# Container status
docker-compose ps vllm-server

# Port binding
docker port vllm-server

# Logs
docker-compose logs vllm-server

# Health
curl http://localhost:8001/health
```

**Wait Time**: First startup takes 2-5 minutes to download and load the model.

### Model Not Found

**Issue**: "Model not found" errors

**Solution**:
Ensure the model name matches exactly:
```yaml
# Correct
--model ByteDance-Seed/UI-TARS-1.5-7B

# Wrong
--model UI-TARS-1.5-7B
--model ByteDance/UI-TARS-1.5-7B
```

## Advanced Configuration

### Custom Sampling Parameters

```yaml
command: >
  --model ByteDance-Seed/UI-TARS-1.5-7B
  --tensor-parallel-size 2
  --max-model-len 8192
  --temperature 0.8
  --top-p 0.95
  --top-k 50
```

### Quantization (Lower Memory)

```yaml
command: >
  --model ByteDance-Seed/UI-TARS-1.5-7B
  --quantization awq
  --tensor-parallel-size 1
```

Note: Model must support quantization format.

### Distributed Inference (4+ GPUs)

```yaml
vllm-server:
  environment:
    - CUDA_VISIBLE_DEVICES=0,1,2,3
  command: >
    --model ByteDance-Seed/UI-TARS-1.5-7B
    --tensor-parallel-size 4
    --pipeline-parallel-size 1
```

## API Documentation

The vLLM server implements the OpenAI API specification:

- **Completions**: `POST /v1/completions`
- **Chat Completions**: `POST /v1/chat/completions`
- **Models**: `GET /v1/models`
- **Health**: `GET /health`

Full API docs: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html

## Performance Benchmarks

On 2x A100 40GB GPUs:
- **Cold Start**: 2-3 minutes (model download + loading)
- **Warm Start**: 30-60 seconds (model loading only)
- **Inference**: 20-50 tokens/second (depends on batch size)
- **Latency**: 100-300ms for first token

## Best Practices

1. **Pre-download models** before production deployment
2. **Use tensor parallelism** for models > 13B parameters
3. **Enable prefix caching** for repeated prompts
4. **Monitor GPU memory** and adjust utilization
5. **Set appropriate max-model-len** based on use case
6. **Use health checks** to ensure server readiness

## Resources

- vLLM Documentation: https://docs.vllm.ai/
- UI-TARS Model: https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B
- OpenAI API Spec: https://platform.openai.com/docs/api-reference
- InfantAgent Issues: https://github.com/bin123apple/InfantAgent/issues

## Support

For vLLM-specific issues:
- vLLM GitHub: https://github.com/vllm-project/vllm
- vLLM Discord: https://discord.gg/vllm

For InfantAgent integration:
- GitHub Issues: https://github.com/bin123apple/InfantAgent/issues
