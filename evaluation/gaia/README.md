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