import io
import re
import os
import json
import torch
import base64
import argparse
import itertools
import warnings
from PIL import Image
from pathlib import Path
import torch.distributed as dist
from vllm import LLM, SamplingParams

warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

GT_TYPES = ['positive', 'negative']
INSTRUCTION_STYLES = ['instruction', 'action', 'description']
LANGUAGES = ['en', 'cn']

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_name', type=str, required=True, help="Path to the pretrained model")
    parser.add_argument('--inst_style', type=str, required=True, choices=INSTRUCTION_STYLES + ['all'], help="Instruction style to use")
    parser.add_argument('--language', type=str, required=True, choices=LANGUAGES + ['all'], help="Language to use")
    parser.add_argument('--gt_type', type=str, required=True, choices=GT_TYPES + ['all'], help="Ground truth type")
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

def eval_sample_positive_gt(sample, point):
    bbox = sample["bbox"]
    # bbox = [bbox[0] / img_size[0], bbox[1] / img_size[1], bbox[2] / img_size[0], bbox[3] / img_size[1]]
    click_point = point
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


def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')


def extract_coordinates(result: list[str]):
    text = result[0].strip()

    # 如果有 <answer> 标签，就提取标签内的内容；否则就直接用 text
    answer_match = re.search(r'<answer>\s*(.*?)\s*</answer>', text, re.DOTALL)
    if answer_match:
        content = answer_match.group(1)
    else:
        content = text  

    # 按 (x, y) 形式提取
    point_match = re.search(r'\(\s*(\d+)\s*,\s*(\d+)\s*\)', content)
    if point_match:
        x, y = map(int, point_match.groups())
        return (x, y)

    # 如果是 (x1, y1, x2, y2) 形式，取中心点
    box_match = re.search(r'\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', content)
    if box_match:
        x1, y1, x2, y2 = map(int, box_match.groups())
        return ((x1 + x2)//2, (y1 + y2)//2)

    return None


def load_screenspot_dataset(base_dir: str):
    """
    加载 ScreenSpot-Pro 本地数据集。

    Args:
        base_dir: 数据集根目录路径，下面应包含 annotations/ 和 images/ 子目录。

    Returns:
        List[dict]: 每个 dict 是一条 annotation，额外包含 "full_img_path" 键。
    """
    base = Path(base_dir)
    ann_dir = base / "annotations"
    img_dir = base / "images"

    all_entries = []
    # 遍历所有 annotation 文件
    for ann_file in ann_dir.glob("*.json"):
        with open(ann_file, "r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError as e:
                print(f"✖️ Parse {ann_file} fail: {e}")
                continue

        # 为每条 annotation 加上图片绝对路径
        for entry in entries:
            rel_path = entry.get("img_filename", "")
            full_img = img_dir / rel_path
            if not full_img.exists():
                print(f"⚠️ Can not find the figure: {full_img}")
            entry["full_img_path"] = str(full_img.resolve())
            all_entries.append(entry)

    return all_entries

def highlight_and_save_region(image: Image.Image, center: tuple[int, int],
                              half_size_x: int = 600, half_size_y: int = 250) -> tuple[tuple[int, int], bytes]:
    """ 
    以 center 为中心，上下左右各 half_size 像素（超出边界则自动裁剪），
    在原图副本上画红色矩形，并保存：
      1. 带标注的整图
      2. 裁剪出的矩形区域
    
    返回 (annotated_path, cropped_path)
    """
    # 1. 计算边界
    width, height = image.size
    x, y = center
    left = max(0, x - half_size_x)
    top = max(0, y - half_size_y)
    right = min(width, x + half_size_x)
    bottom = min(height, y + half_size_y)
    
    if left >= right or top >= bottom:
        raise ValueError(f"Invalid region: {(left, top, right, bottom)}")
    cropped = image.crop((left, top, right, bottom))

    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG") 
    cropped_bytes = buffer.getvalue()
    
    offset = (left, top)
    return offset, cropped_bytes


class OSS_LLM:
    def __init__(self, args):
        self.args = args
        self.model = args.model_name
        self.tokenizer = args.model_name
        self.oss_llm = None
        self.oss_llm_init()
    
    def oss_llm_init(self):
        if self.oss_llm is None:
            self.oss_llm = LLM(
                model=self.model,
                tokenizer=self.model,
                tensor_parallel_size=4,
                gpu_memory_utilization=0.9,
                enforce_eager=True,
                max_model_len=19264,
                disable_custom_all_reduce=True,
                enable_prefix_caching=False,
                trust_remote_code=True,
            )
            
    def oss_llm_completion(self, messages, stop=None):
        sampling_params = SamplingParams(
                    n=1,
                    max_tokens=9632,
                    temperature=0,
                    top_p=1.0,
                    frequency_penalty=0,
                    presence_penalty=0
                )  
        sampling_params.stop = stop
        request_output = self.oss_llm.chat(messages, sampling_params)
        response_list = []
        for response in request_output[0].outputs:
            response_list.append(response.text)
        return response_list

    def _ask_llm(self, image_bytes: bytes, text: str) -> tuple[int,int]:
        b64: str = encode_image(image_bytes)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": text},
                ]
            }
        ]
        result = self.oss_llm_completion(messages)
        return result 


def main():
    args = parse_args()
    
    # Load model
    tester = OSS_LLM(args)
    
    # prepare test data
    base_directory = "screenspot_pro_dataset"
    dataset = load_screenspot_dataset(base_directory)
    system_prompt = (
        "Output only the coordinate of one point in your response. "
        "What element matches the following task: {instruction}"
    )  # based on https://github.com/bytedance/UI-TARS/issues/6
    
    output_path = "predictions.jsonl"
    processed = set()
    # 如果文件已存在，先读出已经写过的 img_path（或其他唯一标识）
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as fin:
            for line in fin:
                try:
                    rec = json.loads(line)
                    # 假设我们用 img_path 来去重
                    processed.add(rec["img_path"])
                except json.JSONDecodeError:
                    continue
    
    # 用追加模式打开，不会覆盖旧数据
    with open(output_path, "a", encoding="utf-8") as fout:
        all_outputs = []
        for data in dataset:
            key = data["img_filename"]  # 或者 data["full_img_path"]
            if key in processed:
                # 跳过已处理过的 case
                continue
    
            image_path = data["full_img_path"]
            # 1) 读二进制图像
            with open(image_path, 'rb') as f:
                byte_image = f.read()
    
            # 2) 根据语言选择 instruction
            if args.language == "cn":
                instruction_format = system_prompt.format(instruction=data["instruction_cn"])
            else:
                instruction_format = system_prompt.format(instruction=data["instruction"])
    
            # 3) 第一次询问
            response = tester._ask_llm(byte_image, instruction_format)
            print(f"Response: {response}")  # for debugging
            point = extract_coordinates(response)
    
            # 4) 如果有 point，再做本地 crop+highlight+二次询问
            if point and isinstance(point, tuple) and len(point) == 2:
                img = Image.open(image_path).convert("RGB")
                (dx, dy), byte_img = highlight_and_save_region(
                    img, point,
                    half_size_x=700, half_size_y=250
                )
                response = tester._ask_llm(byte_img, instruction_format)
                print(f"Response: {response}")  # for debugging
                point = extract_coordinates(response)
                if point:
                    point = (point[0] + dx, point[1] + dy)
                else:
                    point = None
    
            # 5) 评估正负样本
            correctness = eval_sample_positive_gt(data, point)
    
            # 6) 构造输出字典
            sample_result = {
                "model_name": args.model_name,
                "img_path": key,
                "group": data.get("group"),
                "platform": data["platform"],
                "application": data["application"],
                "gt_type": args.gt_type,
                "instruction_style": args.inst_style,
                "lang": args.language,
                "ui_type": data.get("ui_type"),
                "pred": point,
                "correctness": correctness
            }
            if data.get("gt_type") == "positive":
                sample_result["bbox"] = data["bbox"]
    
            # 7) 写入并记录
            fout.write(json.dumps(sample_result, ensure_ascii=False) + "\n")
            processed.add(key)
            all_outputs.append(sample_result)
    
    # evaluate
    result_report = evaluate(all_outputs)
    print(f"Evaluation Result: {result_report}")
    print(f"Finish writing results to {output_path}, {len(all_outputs)} new samples.")

if __name__ == "__main__":
    main()