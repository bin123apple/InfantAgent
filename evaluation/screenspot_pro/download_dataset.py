from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="likaixin/ScreenSpot-Pro",
    repo_type="dataset",
    allow_patterns=["annotations/**", "images/**"],  
    local_dir="screenspot_pro_dataset",         
)
