# SWE-Bench Evaluation 

## Run inference

```
export OPENAI_API_KEY='Your LLM API Key'
python run_inference.py
```

## Evaluation

```
python -m evaluation \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --predictions_path YOUR_OWN_predictions.jsonl \
    --max_workers 8 \
    --run_id evaluation
```

## Final format
```
.
├── Dockerfile
├── evaluation.py
├── gpt-4o.evaluation.json
├── instance_swe_entry.sh
├── logs
│   ├── build_images
│   │   ├── base
│   │   │   └── sweb.base.py.x86_64__latest
│   │   │       ├── build_image.log
│   │   │       └── Dockerfile
│   │   ├── env
│   │   │   └── sweb.env.py.x86_64.428468730904ff6b4232aa__latest
│   │   │       ├── build_image.log
│   │   │       ├── Dockerfile
│   │   │       └── setup_env.sh
│   │   └── instances
│   │       └── sweb.eval.x86_64.astropy__astropy-12907__latest
│   │           ├── build_image.log
│   │           ├── Dockerfile
│   │           └── setup_repo.sh
│   └── run_evaluation
│       └── evaluation
│           └── gpt-4o
│               ├── astropy__astropy-12907
│               │   ├── eval.sh
│               │   ├── patch.diff
│               │   ├── report.json
│               │   ├── run_instance.log
│               │   └── test_output.txt
│               └── astropy__astropy-14182
│                   ├── eval.sh
│                   ├── patch.diff
│                   ├── report.json
│                   ├── run_instance.log
│                   └── test_output.txt
├── predictions.jsonl
├── README.md
└── run_inference.py
```

## Performance

All the predictions.jsonl files are stored in predictions folder 

| Model            | Agent Version          | dataset        | Accuracy     |
|:------------------:|:---------------------:|:-------------------:|:------------:|
| DeepSeek-V3-0324           | InfantAgent-2025-04-01   | SWE-Bench-Lite    | 29.3%        |
| Claude-3.7-Sonnet| InfantAgent-2025-04-01  | SWE-Bench-Verified         | TODO       |

