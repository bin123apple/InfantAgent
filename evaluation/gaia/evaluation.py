#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import string
import warnings
from collections import defaultdict
from typing import Dict, List, Tuple

# —— 辅助函数 —— #

def normalize_number_str(number_str: str) -> float:
    for char in ["$", "%", ","]:
        number_str = number_str.replace(char, "")
    try:
        return float(number_str)
    except ValueError:
        print(f"String {number_str!r} cannot be normalized to number str.")
        return float("inf")


def split_string(s: str, char_list: List[str] = [",", ";"]) -> List[str]:
    pattern = f"[{''.join(char_list)}]"
    return re.split(pattern, s)


def normalize_str(input_str: str, remove_punct: bool = True) -> str:
    # 去掉所有空白
    no_spaces = re.sub(r"\s+", "", input_str)
    if remove_punct:
        translator = str.maketrans("", "", string.punctuation)
        return no_spaces.lower().translate(translator)
    else:
        return no_spaces.lower()


def question_scorer(model_answer: str, ground_truth: str) -> bool:
    def is_float(elem: str) -> bool:
        try:
            float(elem)
            return True
        except ValueError:
            return False

    if model_answer is None:
        model_answer = ""

    # 数值题
    if is_float(ground_truth):
        normalized = normalize_number_str(model_answer)
        return normalized == float(ground_truth)

    # 列表题（逗号或分号）
    if any(c in ground_truth for c in [",", ";"]):
        gt_elems = split_string(ground_truth)
        ma_elems = split_string(model_answer)
        if len(gt_elems) != len(ma_elems):
            warnings.warn("List does not have the same length False", UserWarning)
            return False
        for ma, gt in zip(ma_elems, gt_elems):
            if is_float(gt):
                if normalize_number_str(ma) != float(gt):
                    return False
            else:
                if normalize_str(ma, remove_punct=False) != normalize_str(gt, remove_punct=False):
                    return False
        return True

    # 普通字符串题
    return normalize_str(model_answer) == normalize_str(ground_truth)


def load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


# —— 主逻辑 —— #

def main(
    preds_path: str,
    meta_path: str,
):
    # 1. 读 ground truth 和 level
    gt_dict: Dict[str, str]    = {}
    level_dict: Dict[str, str] = {}
    for entry in load_jsonl(meta_path):
        tid = entry.get("task_id")
        if tid is None:
            continue
        gt_dict[tid]    = entry.get("Final answer", "")
        # metadata 中可能字段名是 "level" 或 "Level"
        level_dict[tid] = entry.get("level", entry.get("Level", "Unknown"))

    # 2. 准备提取 FINAL ANSWER 的正则
    final_pat = re.compile(r"FINAL ANSWER:(.*)", re.IGNORECASE)

    # 3. 遍历 predictions
    report: List[Dict] = []
    stats = defaultdict(lambda: {"correct": 0, "total": 0})

    for pred in load_jsonl(preds_path):
        tid    = pred.get("task_id")
        raw    = pred.get("model_answer", "")
        # 提取 FINAL ANSWER: 之后的部分
        m = final_pat.search(raw)
        model_ans = m.group(1).strip() if m else raw.strip()
        gt = gt_dict.get(tid, "")
        lvl = level_dict.get(tid, "Unknown")

        correct = question_scorer(model_ans, gt)
        stats[lvl]["total"]   += 1
        stats[lvl]["correct"] += int(correct)

        report.append({
            "task_id":      tid,
            "level":        lvl,
            "model_answer": model_ans,
            "ground_truth": gt,
            "correct":      correct,
        })

    # 4. 打印详细报告
    print("\n—— 详细报告 ——\n")
    for r in report:
        status = "✅ Correct" if r["correct"] else "❌ Wrong"
        print(
            f"Task {r['task_id']} (Level {r['level']}): {status}\n"
            f"  prediction: {r['model_answer']}\n"
            f"  groundtruth: {r['ground_truth']}\n"
        )
    accuracy = sum(r['correct'] for r in report) / len(report)
    print(f"Total Accuracy: {accuracy*100:.2f}%\n")
    
    # 5. 打印分级准确率
    print("\n—— Accuray of each level ——\n")
    for lvl in sorted(stats.keys(), key=lambda x: (x=="Unknown", x)):
        tot = stats[lvl]["total"]
        corr = stats[lvl]["correct"]
        acc = corr / tot * 100 if tot else 0.0
        print(f"Level {lvl}: {corr}/{tot} = {acc:.2f}%")

if __name__ == "__main__":
    preds_file = "predictions.jsonl"
    meta_file  = "gaia_dataset/2023/validation/metadata.jsonl"
    main(preds_file, meta_file)
