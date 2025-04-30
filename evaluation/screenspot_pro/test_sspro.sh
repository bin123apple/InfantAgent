# export CUDA_VISIBLE_DEVICES=7 && export NCCL_IB_DISABLE="1" && export NCCL_P2P_DISABLE="1" && torchrun --nproc_per_node="1" test_rec_r1.py

export CUDA_VISIBLE_DEVICES=4,5,6,7
export NCCL_IB_DISABLE="1"
export NCCL_P2P_DISABLE="1"

torchrun --nproc_per_node="4" --master_port="13121" test_rec_r1_sspro.py  \
        --model_path /data_ext1/kangweitai/gui/output/RL-AdaptSmallKL-PointCheck-softFormat-PointPred/checkpoint-500  \
        --screenspot_imgs "/data_ext1/kangweitai/gui/ScreenSpotPro/images"  \
        --screenspot_test "/data_ext1/kangweitai/gui/ScreenSpotPro/annotations"  \
        --task "all" \
        --language "en" \
        --gt_type "positive" \
        --inst_style "instruction" \
        --batch_size 1 \