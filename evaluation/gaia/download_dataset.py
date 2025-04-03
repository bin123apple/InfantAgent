from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="gaia-benchmark/GAIA",
    repo_type="dataset",
    allow_patterns="2023/validation/**",  
    local_dir="gaia_dataset",         
)
