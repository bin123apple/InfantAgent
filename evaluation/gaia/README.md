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
| Claude-3.7-Sonnet          | InfantAgent-2025-04-01   | SWE-Bench-Lite    | 29.3%        |
| Claude-3.7-Sonnet| InfantAgent-2025-04-01  | SWE-Bench-Verified         | TODO       |