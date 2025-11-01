# GAIA Evaluation  

## Download dataset
```
cd evaluation/gaia
huggingface-cli login # input your huggingface token
python download_dataset.py
```

##  Build Base Image
```
docker build -t gaia_base_image -f Dockerfile .
```

## Run inference 

Setup vllm server
```
export CUDA_VISIBLE_DEVICES=4
python -m vllm.entrypoints.openai.api_server \
  --model ByteDance-Seed/UI-TARS-1.5-7B \
  --host 0.0.0.0 --port 8000 \
  --trust-remote-code \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.9
```

run
```
export OPENAI_API_KEY='YOUR KEY'
export ANTHROPIC_API_KEY='YOUR KEY'
export VLLM_BASE_URL="http://127.0.0.1:8000"
python run_inference.py
```

## Evaluation
```
python evaluation.py
```

## Performance
All the predictions.jsonl files are stored in predictions folder 

| Model            | Visual localization Model            | Agent Version          | dataset        | Accuracy     |
|:------------------:|:------------------:|:---------------------:|:-------------------:|:------------:|
| Claude-3.7-Sonnet   |RL-Qwen2.5VL-lora-7B-ckpt500| InfantAgent-2025-04-15   | gaia-validation    | 56.97%        |
| o4-mini |-| - | -       | TODO       |