# ScreenSpot-Pro Evaluation  

The purpose of this set of experiments is to verify the improvement in visual localization achieved by our method: generate coordinates → crop the image → regenerate coordinates—for visual localization.

## Download dataset
```
cd evaluation/screenspot_pro
huggingface-cli login # input your huggingface token
python download_dataset.py
```

## Run 
```
python run_inference.py \
  --model_name ByteDance-Seed/UI-TARS-1.5-7B \
  --inst_style instruction \
  --language cn \
  --gt_type positive
```

## Performance

| Model            |  feedback turns       | dataset        | Accuracy     |
|:------------------:|:------------------:|:---------------------:|:------------:|
| UI-TARS-1.5-7B (zero-shot)  |0|   screenspot-pro-cn    | 38.20%        |
| UI-TARS-1.5-7B   |1|   screenspot-pro-cn    | 48.07%        |
| UI-TARS-1.5-7B  (zero-shot) |0|   screenspot-pro-en    | 39.66%        |
| UI-TARS-1.5-7B   |1|   screenspot-pro-en    | 48.45%        |

