# OSWorld Evaluation  (Unfinished)

## Download dataset
The source dataset is from `https://github.com/xlang-ai/OSWorld/tree/main/evaluation_examples`

##  Build Base Image
```
docker build -t gaia_base_image -f Dockerfile .
```

## Run inference 
```
export ANTHROPIC_API_KEY='YOUR KEY'
python run_inference.py
```
