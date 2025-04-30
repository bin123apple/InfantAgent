import os
import json
import re
import argparse
import copy
import itertools
import warnings
from PIL import Image
import numpy as np
from tqdm import tqdm
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import smart_resize
import random

warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

GT_TYPES = ['positive', 'negative']
INSTRUCTION_STYLES = ['instruction', 'action', 'description']
LANGUAGES = ['en', 'cn']

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', type=str, required=True, help="Path to the pretrained model")
    parser.add_argument('--screenspot_imgs', type=str, required=True, help="Path to ScreenSpot images")
    parser.add_argument('--screenspot_test', type=str, required=True, help="Path to ScreenSpot test JSON files")
    parser.add_argument('--task', type=str, required=True, help="Task filename(s) or 'all'")
    parser.add_argument('--inst_style', type=str, required=True, choices=INSTRUCTION_STYLES + ['all'], help="Instruction style to use")
    parser.add_argument('--language', type=str, required=True, choices=LANGUAGES + ['all'], help="Language to use")
    parser.add_argument('--gt_type', type=str, required=True, choices=GT_TYPES + ['all'], help="Ground truth type")
    # parser.add_argument('--log_path', type=str, required=True, help="Path to save results")
    parser.add_argument('--batch_size', type=int, default=3, help="Batch size per GPU")
    parser.add_argument('--steps', type=int, default=500, help="Checkpoint steps")
    return parser.parse_args()

def setup_distributed():
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    dist.init_process_group(backend="nccl")
    world_size = dist.get_world_size()
    rank = dist.get_rank()
    return local_rank, world_size, rank

def pointinbbox(pred_point, gt_bbox):
    if (gt_bbox[0] <= pred_point[0] <= gt_bbox[2]) and (gt_bbox[1] <= pred_point[1] <= gt_bbox[3]):
        return True
    return False

def extract_point_answer(content):
    answer_tag_pattern = r'<answer>(.*?)</answer>'
    point_pattern = r'(\d+\.?\d*(?:\s*[,;\s]\s*|\s+)\d+\.?\d*)'
    content_answer_match = re.search(answer_tag_pattern, content, re.DOTALL)
    if content_answer_match:
        content_answer = content_answer_match.group(1).strip()
        point_match = re.search(point_pattern, content_answer, re.DOTALL)
        if point_match:
            point_str = point_match.group(1)
            point = [float(x) for x in re.findall(r'\d+\.?\d*', point_str)]
            if len(point) >= 2:
                point = point[:2]
            else:
                point = [0, 0]
            return point
    return [0, 0]

def eval_sample_positive_gt(sample, response, img_size):
    bbox = sample["bbox"]
    # bbox = [bbox[0] / img_size[0], bbox[1] / img_size[1], bbox[2] / img_size[0], bbox[3] / img_size[1]]
    click_point = response["point"]
    if click_point is None:
        return "wrong_format"
    if pointinbbox(click_point, bbox):
        return "correct"
    return "wrong"

def eval_sample_negative_gt(sample, response):
    if response["result"] == "negative":
        return "correct"
    elif response["result"] == "positive":
        return "wrong"
    return "wrong_format"

def collect_results_to_eval(results, platform=None, group=None, application=None, language=None, gt_type=None, instruction_style=None, ui_type=None):
    filtered_results = []
    for sample in results:
        if (platform is None or sample.get("platform") == platform) and \
           (group is None or sample.get("group") == group) and \
           (application is None or sample.get("application") == application) and \
           (language is None or sample.get("language") == language) and \
           (gt_type is None or sample.get("gt_type") == gt_type) and \
           (instruction_style is None or sample.get("instruction_style") == instruction_style) and \
           (ui_type is None or sample.get("ui_type") == ui_type):
            filtered_results.append(sample)
    return filtered_results

def make_combinations(results, platform=False, group=None, application=False, language=False, gt_type=False, instruction_style=False, ui_type=False):
    unique_values = {
        "platform": set(),
        "group": set(),
        "application": set(),
        "language": set(),
        "gt_type": set(),
        "instruction_style": set(),
        "ui_type": set(),
    }
    for sample in results:
        if platform:
            unique_values["platform"].add(sample.get("platform"))
        if group:
            unique_values["group"].add(sample.get("group"))
        if application:
            unique_values["application"].add(sample.get("application"))
        if language:
            unique_values["language"].add(sample.get("language"))
        if gt_type:
            unique_values["gt_type"].add(sample.get("gt_type"))
        if instruction_style:
            unique_values["instruction_style"].add(sample.get("instruction_style"))
        if ui_type:
            unique_values["ui_type"].add(sample.get("ui_type"))
    filtered_values = {key: list(value) for key, value in unique_values.items() if value}
    if not filtered_values:
        return []
    attribute_combinations = list(itertools.product(*filtered_values.values()))
    combinations = [dict(zip(filtered_values.keys(), combination)) for combination in attribute_combinations]
    return combinations

def calc_metric_for_result_list(results):
    num_total = len(results)
    correct_num = sum(1 for res in results if res["correctness"] == "correct")
    wrong_format_num = sum(1 for res in results if res["correctness"] == "wrong_format")
    text_results = collect_results_to_eval(results, ui_type="text")
    icon_results = collect_results_to_eval(results, ui_type="icon")
    text_correct = sum(1 for res in text_results if res["correctness"] == "correct")
    text_total = len(text_results)
    icon_correct = sum(1 for res in icon_results if res["correctness"] == "correct")
    icon_total = len(icon_results)
    metrics = {
        "num_correct_action": correct_num,
        "num_total": num_total,
        "wrong_format_num": wrong_format_num,
        "action_acc": correct_num / num_total if num_total > 0 else 0,
        "text_acc": text_correct / text_total if text_total > 0 else 0,
        "icon_acc": icon_correct / icon_total if icon_total > 0 else 0
    }
    return metrics

def evaluate_fine_grained(results):
    combinations = make_combinations(
        results, 
        platform=True, 
        application=True,
        instruction_style=True, 
        gt_type=True
    )
    evaluation_result = {}
    for combo in combinations:
        platform = combo.get("platform")
        application = combo.get("application")
        inst_style = combo.get("instruction_style")
        gt_type = combo.get("gt_type")
        filtered_results = collect_results_to_eval(
            results=results,
            platform=platform,
            application=application,
            instruction_style=inst_style,
            gt_type=gt_type
        )
        metrics = calc_metric_for_result_list(filtered_results)
        if metrics['num_total'] == 0:
            continue
        key = f"plat:{platform} app:{application} inst_style:{inst_style} gt_type:{gt_type}"
        evaluation_result[key] = metrics
    return evaluation_result

def evaluate_seeclick_paper_style(results):
    combinations = make_combinations(
        results, 
        platform=True, 
        instruction_style=True, 
        gt_type=True
    )
    evaluation_result = {}
    for combo in combinations:
        platform = combo.get("platform")
        inst_style = combo.get("instruction_style")
        gt_type = combo.get("gt_type")
        filtered_results = collect_results_to_eval(
            results=results,
            platform=platform,
            instruction_style=inst_style,
            gt_type=gt_type
        )
        metrics = calc_metric_for_result_list(filtered_results)
        if metrics['num_total'] == 0:
            continue
        key = f"plat:{platform} inst_style:{inst_style} gt_type:{gt_type}"
        evaluation_result[key] = metrics
    return evaluation_result

def evaluate_leaderboard_detailed_style(results):
    combinations = make_combinations(
        results, 
        application=True,
    )
    evaluation_result = {}
    for combo in combinations:
        application = combo.get("application")
        filtered_results = collect_results_to_eval(
            results=results,
            application=application,
        )
        metrics = calc_metric_for_result_list(filtered_results)
        if metrics['num_total'] == 0:
            continue
        key = f"app:{application}"
        evaluation_result[key] = metrics
    return evaluation_result

def evaluate_leaderboard_simple_style(results):
    combinations = make_combinations(
        results, 
        group=True,
    )
    evaluation_result = {}
    for combo in combinations:
        group = combo.get("group")
        filtered_results = collect_results_to_eval(
            results=results,
            group=group,
        )
        metrics = calc_metric_for_result_list(filtered_results)
        if metrics['num_total'] == 0:
            continue
        key = f"group:{group}"
        evaluation_result[key] = metrics
    return evaluation_result

# def evaluate_leaderboard_simple_style(results):
#     combinations = make_combinations(
#         results, 
#         group=True,
#         ui_type=True
#     )
#     evaluation_result = {}
#     for combo in combinations:
#         group = combo.get("group")
#         ui_type = combo.get("ui_type")
#         filtered_results = collect_results_to_eval(
#             results=results,
#             group=group,
#             ui_type=ui_type
#         )
#         metrics = calc_metric_for_result_list(filtered_results)
#         if metrics['num_total'] == 0:
#             continue
#         key = f"group:{group} ui_type:{ui_type}"
#         evaluation_result[key] = metrics
#         print(f"Accuracy for group:{group}, ui_type:{ui_type}: {metrics['action_acc']:.4f} ({metrics['num_correct_action']}/{metrics['num_total']})")
#     return evaluation_result

def evaluate_overall(results):
    metrics = calc_metric_for_result_list(results)
    return metrics

def evaluate(results):
    result_report = {
        "details": results,
        "metrics": {
            # "fine_grained": evaluate_fine_grained(results),
            # "seeclick_style": evaluate_seeclick_paper_style(results),
            "leaderboard_simple_style": evaluate_leaderboard_simple_style(results),
            "leaderboard_detailed_style": evaluate_leaderboard_detailed_style(results),
            "overall": evaluate_overall(results)
        }
    }
    return result_report

def main():
    args = parse_args()
    local_rank, world_size, rank = setup_distributed()
    device = f"cuda:{local_rank}"
    if rank == 0:
        print(f"Running with {world_size} GPUs, batch size per GPU: {args.batch_size}")

    # Load model and processor
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model_path,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
        device_map={"": local_rank},
    )
    processor = AutoProcessor.from_pretrained(args.model_path)
    model = model.to(device)

    # Prepare tasks
    if args.task == "all":
        task_filenames = [os.path.splitext(f)[0] for f in os.listdir(args.screenspot_test) if f.endswith(".json")]
    else:
        task_filenames = args.task.split(",")

    if args.inst_style == "all":
        inst_styles = INSTRUCTION_STYLES
    else:
        inst_styles = args.inst_style.split(",")

    if args.language == "all":
        languages = LANGUAGES
    else:
        languages = args.language.split(",")

    if args.gt_type == "all":
        gt_types = GT_TYPES
    else:
        gt_types = args.gt_type.split(",")

    tasks_to_run = []
    for task_filename in task_filenames:
        dataset = task_filename + ".json"
        with open(os.path.join(args.screenspot_test, dataset), 'r') as f:
            task_data = json.load(f)
        for inst_style in inst_styles:
            for gt_type in gt_types:
                for lang in languages:
                    for task_instance in task_data:
                        task_instance = copy.deepcopy(task_instance)
                        task_instance["task_filename"] = task_filename
                        task_instance["gt_type"] = gt_type
                        task_instance["instruction_style"] = inst_style
                        task_instance["language"] = lang
                        if lang == "cn":
                            if inst_style != 'instruction' or gt_type != 'positive':
                                continue  # Skip unsupported combinations
                            task_instance["prompt_to_evaluate"] = task_instance["instruction_cn"]
                        elif lang == "en":
                            task_instance["prompt_to_evaluate"] = task_instance["instruction"]
                        tasks_to_run.append(task_instance)
        
        # demo_length = 20
        # random.shuffle(tasks_to_run)
        # tasks_to_run = tasks_to_run[:demo_length]
        if rank == 0:
            print(f"Num of samples in {task_filename}: {len(task_data)} * {len(inst_styles)} * {len(gt_types)} * {len(languages)}")

    if rank == 0:
        print(f"Total tasks: {len(tasks_to_run)}")

    # Split data across GPUs
    per_rank_data = len(tasks_to_run) // world_size
    start_idx = rank * per_rank_data
    end_idx = start_idx + per_rank_data if rank < world_size - 1 else len(tasks_to_run)
    rank_data = tasks_to_run[start_idx:end_idx]

    # Prepare messages for model inference
    prefix = 'Please provide the point coordinates [x, y] of a specific element based on this sentence: '
    suffix = ' First, think about the reasoning process in the mind within <think> </think> tags. Then, output the point coordinates within <answer> </answer> tags.'
    QUESTION_TEMPLATE = prefix + "{Question}" + suffix
    # patch_size, merge_size, min_pixels, max_pixels = 14, 2, 4 * 28 * 28, 16384 * 28 * 28

    messages = []
    # all_img_ratio = []
    for x in rank_data:
        image_path = os.path.join(args.screenspot_imgs, x['img_filename'])
        # image = Image.open(image_path)
        # width, height = image.size
        # resized_height, resized_width = smart_resize(
        #     height, width, factor=patch_size * merge_size, min_pixels=min_pixels, max_pixels=max_pixels
        # )
        question = x['prompt_to_evaluate'].strip('.').strip() + '.'
        message = [{
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{image_path}"},
                {"type": "text", "text": QUESTION_TEMPLATE.format(Question=question)}
            ]
        }]
        messages.append(message)
        # all_img_ratio.append([width / resized_width, height / resized_height])

    rank_outputs = []
    for i in tqdm(range(0, len(messages), args.batch_size), disable=rank != 0):
        batch_rank_data = rank_data[i:i + args.batch_size]
        batch_messages = messages[i:i + args.batch_size]
        # batch_img_ratio = all_img_ratio[i:i + args.batch_size]
        text = [processor.apply_chat_template(msg, tokenize=False, add_generation_prompt=True) for msg in batch_messages]
        image_inputs, video_inputs = process_vision_info(batch_messages)
        inputs = processor(
            text=text, images=image_inputs, videos=video_inputs, padding=True, padding_side="left", return_tensors="pt"
        )
        inputs = inputs.to(device)
        generated_ids = model.generate(**inputs, use_cache=True, max_new_tokens=1024, do_sample=False)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        batch_output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )

        for each_output_text, each_data in zip(batch_output_text, batch_rank_data):
            pred_point = extract_point_answer(each_output_text)
            img_size = each_data["img_size"]
            # point_in_pixel = [pred_point[0] * img_size[0], pred_point[1] * img_size[1]] if pred_point != [0, 0] else None
            point_in_pixel = pred_point
            response = {"point": pred_point, "raw_response": each_output_text}
            if each_data["gt_type"] == "positive":
                correctness = eval_sample_positive_gt(each_data, response, img_size)
            else:
                response["result"] = "positive" if pred_point != [0, 0] else "negative"
                correctness = eval_sample_negative_gt(each_data, response)

            sample_result = {
                "img_path": os.path.join(args.screenspot_imgs, each_data["img_filename"]),
                "group": each_data.get("group"),
                "platform": each_data["platform"],
                "application": each_data["application"],
                "lang": each_data["language"],
                "instruction_style": each_data["instruction_style"],
                "prompt_to_evaluate": each_data["prompt_to_evaluate"],
                "gt_type": each_data["gt_type"],
                "ui_type": each_data["ui_type"],
                "task_filename": each_data["task_filename"],
                "pred": point_in_pixel,
                "raw_response": response["raw_response"],
                "correctness": correctness
            }
            if each_data["gt_type"] == "positive":
                sample_result["bbox"] = each_data["bbox"]
            rank_outputs.append(sample_result)

    print(f"Rank {rank} processed {len(rank_outputs)} samples")

    # Gather results
    all_outputs = [None] * len(tasks_to_run)
    rank_results = [(start_idx + i, output) for i, output in enumerate(rank_outputs)]
    gathered_results = [None] * world_size
    dist.all_gather_object(gathered_results, rank_results)
    assert gathered_results[-1][-1][0] == len(tasks_to_run) - 1

    # Main process collects and evaluates results
    if rank == 0:
        for results in gathered_results:
            for idx, output in results:
                all_outputs[idx] = output
        assert all_outputs[-1] is not None
        result_report = evaluate(all_outputs)
        # os.makedirs(os.path.dirname(args.log_path), exist_ok=True)
        # with open(args.log_path, "w") as f:
        #     json.dump(result_report, f, indent=4)
        # print(f"Results saved to {args.log_path}")
        print('==='*10)
        print("Metrics:", result_report["metrics"]["overall"])
        print('==='*10)
        # print("Fine-grained metrics:", result_report["metrics"]["fine_grained"])
        # print("SeeClick paper style metrics:", result_report["metrics"]["seeclick_style"])
        # print("Leaderboard detailed style metrics:", result_report["metrics"]["leaderboard_detailed_style"])
        print("Leaderboard simple style metrics:", result_report["metrics"]["leaderboard_simple_style"])
        print('==='*10)


    dist.barrier()

if __name__ == "__main__":
    main()