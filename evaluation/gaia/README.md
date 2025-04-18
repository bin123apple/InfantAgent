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
python run_inference.py

## Evaluation
python evaluation.py

## Performance
All the predictions.jsonl files are stored in predictions folder 

| Model            | Visual localization Model            | Agent Version          | dataset        | Accuracy     |
|:------------------:|:------------------:|:---------------------:|:-------------------:|:------------:|
| Claude-3.7-Sonnet   |RL-Qwen2.5VL-lora-7B-ckpt500| InfantAgent-2025-04-15   | gaia-validation    | 56.97%        |
| o4-mini |-| - | -       | TODO       |