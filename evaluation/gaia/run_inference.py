import os
import uuid
import json
import shutil
import asyncio
import traceback
import subprocess
import concurrent.futures
from infant.config import config, ComputerParams
from infant.agent.agent import Agent
from infant.computer.computer import Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.agent.memory.memory import Userrequest, Finish, IPythonRun
from infant.util.logger import infant_logger as logger
from infant.util.logger import reset_logger_for_multiprocessing, LOG_DIR
from infant.prompt.tools_prompt import IMPORTS
import infant.util.constant as constant
from typing import List, Dict, Any, Optional

def extract_metadata(filename: str) -> List[Dict[str, Any]]:
    """
    读取元数据：
    - 若为 .parquet：使用 pandas 读取并转为 list[dict]
    - 若为 .jsonl/.json：使用逐行 JSON 解析（保留你原本逻辑）
    额外处理：若没有 task_id 但有 id，则重命名为 task_id
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".parquet":
        import pandas as pd  # 需要安装 pyarrow 或 fastparquet
        df = pd.read_parquet(filename)

        # 如果没有 task_id，但有 id，则重命名
        if "task_id" not in df.columns:
            if "id" in df.columns:
                df = df.rename(columns={"id": "task_id"})
            else:
                # 不强制要求一定有 task_id，但给个提醒
                print("[extract_metadata] Warning: parquet 中未找到 `task_id` 列。")

        records = df.to_dict(orient="records")
        # 可选：把 task_id 统一转成 str，避免后面字典键类型不一致
        for r in records:
            if "task_id" in r and r["task_id"] is not None:
                r["task_id"] = str(r["task_id"])
        return records

    # 默认：按 jsonl/json 读取
    records = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # 同样做下 task_id 兼容
                if "task_id" not in data and "id" in data:
                    data["task_id"] = data["id"]
                if "task_id" in data and data["task_id"] is not None:
                    data["task_id"] = str(data["task_id"])
                records.append(data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Line: {line}")
                continue
    return records

def slice_dataset(dataset: List[Dict[str, Any]],
                   index_start: int = 0,
                   index_end: Optional[int] = None) -> List[Dict[str, Any]]:
    """按含头不含尾的切片规则选择一段数据，并做边界与合法性检查。"""
    n = len(dataset)
    if index_end is None:
        index_end = n
    # 规范化：防止负数/越界
    index_start = max(0, index_start)
    index_end = max(0, min(index_end, n))
    if index_start >= index_end:
        print(f"[warn] empty slice: start={index_start}, end={index_end}, total={n}")
        return []
    subset = dataset[index_start:index_end]
    print(f"[info] using subset {index_start}:{index_end} of {n} (size={len(subset)})")
    return subset

async def initialize_docker_agent(instance: dict, config=config)-> Agent:
    # Initialize the API Based LLM
    litellm_parameter = config.get_litellm_params()
    litellm_parameter.gift_key = False
    api_llm = LLM_API_BASED(litellm_parameter)
    
    # Initialize the OSS Based LLM
    if config.use_oss_llm:
        vllm_parameter = config.get_vllm_params()
        vllm_parameter.base_url_oss = os.getenv("VLLM_BASE_URL") # e.g., export VLLM_BASE_URL="http://127.0.0.1:8000"
        oss_llm = LLM_OSS_BASED(vllm_parameter)
    else:
        oss_llm = None
    logger.info(f'LLMs initialized successfully.')
    
    # initialize the computer
    computer_parameter: ComputerParams = config.get_computer_params()
    computer_parameter.computer_container_image = 'gaia_base_image'
    computer_parameter.instance_id = instance['task_id']
    computer_parameter.workspace_mount_path = os.path.join(os.getcwd(), "gaia_workspace", instance['task_id'])
    constant.MOUNT_PATH = computer_parameter.workspace_mount_path
    
    # Use find_available_tcp_port() to find available ports
    computer_parameter.gui_port = None
    computer_parameter.consistant_computer = None
    computer_parameter.ssh_bind_port = None
    computer_parameter.nomachine_bind_port = None
    computer_parameter.run_as_infant = True

    sid = str(uuid.uuid4())
    try:
        computer = Computer(computer_parameter, sid = sid)
    except:
        logger.error({traceback.format_exc()})

    # activate conda
    computer.execute(f'source /infant/miniforge3/etc/profile.d/conda.sh')
    computer.execute('export PATH=/infant/miniforge3/bin:$PATH')
    computer.execute(f'source ~/.bashrc')
    logger.info(f'Conda environment activated successfully.')
        
    # git initial commit 
    computer.execute(f'git init') # initialize git
    computer.execute('git config --global core.pager ""')
    computer.execute(f'git add .') # initial add
    computer.execute(f'git commit -m "base commit"') # initial add
    logger.info(f'Git initialized successfully.')
    computer.execute('source ~/.bashrc')
    
    # set language
    computer.execute("echo 'export LANG=en_US.UTF-8' >> ~/.bashrc")
    computer.execute("echo 'export LC_ALL=en_US.UTF-8' >> ~/.bashrc")
    computer.execute("source ~/.bashrc")

    # Initialize the Agent
    agent_parameter = config.get_agent_params()
    agent_parameter.fake_response_mode = True
    agent_parameter.max_budget_per_task = 10
    agent = Agent(agent_config = agent_parameter, planning_llm = api_llm, execution_llm = api_llm,
                  fe_llm = api_llm, tm_llm = api_llm, vg_llm = oss_llm, computer = computer)
    logger.info(f'Agent initialized successfully.')
    
    import_memory = IPythonRun(code = IMPORTS)
    await computer.run_ipython(import_memory)
    
    import_memory = IPythonRun(code = "press_key('Escape')")
    await computer.run_ipython(import_memory)
    
    # set up initial environment
    computer.execute(f'sudo DEBIAN_FRONTEND=noninteractive apt remove -s -y gnome-keyring')
    return agent

def process_instance(instance: dict):
    instance_id = instance['task_id']

    reset_logger_for_multiprocessing(logger, instance_id, LOG_DIR)

    try:
        formatted_answer, reasoning_trace = asyncio.run(run_single_instance(instance, logger))
        logger.info("Finish processing instance: %s", instance_id)
        cleanup_docker(instance)
        logger.info("Cleanup docker successfully")
    except Exception as e:
        logger.exception("Fail to process instance %s Error: %s", instance_id, e)
        cleanup_docker(instance)
        logger.info("Cleanup docker successfully")
        raise e

    return formatted_answer, reasoning_trace

async def run_single_step(agent: Agent, user_request_text: str):
    agent.state.memory_list.append(Userrequest(text=user_request_text))
    await agent.state.memory_queue.put(agent.state.memory_list[-1])

    monitor_task = asyncio.create_task(agent.monitor_agent_state())
    special_case_task = asyncio.create_task(agent.special_case_handler())
    step_task = asyncio.create_task(agent.step())
    
    await monitor_task

    if not step_task.done():
        step_task.cancel() 
        try:
            await step_task
        except asyncio.CancelledError:
            logger.info("Step task has been cancelled")
    
    if not special_case_task.done():
        special_case_task.cancel()
        try:
            await special_case_task
        except asyncio.CancelledError:
            logger.info("Special case task has been cancelled")

    finish_memory: Finish = agent.state.memory_list[-1]
    answer = finish_memory.thought
    return answer

async def run_single_instance(instance: dict, logger):
    # Initialize the docker and the Agent
    agent = await initialize_docker_agent(instance=instance, config=config)
    task_id: str = instance.get("task_id", "unknown")
    logger.info(f"Running instance: {task_id}")

    # prepare the user request text/files
    whether_attach_file = False
    problem_statement: str = instance.get("Question", "unknown")
    file_name = instance.get("file_name", "")
    if not file_name == "":
        whether_attach_file = True
        file_path = os.path.join("gaia_dataset/2023/validation", file_name)
        dest_path = os.path.join(agent.computer.workspace_mount_path, file_name)
        shutil.copy(file_path, dest_path)
        _, ext = os.path.splitext(file_path)

    user_request = (
        f"I have attached the {ext} file: {file_name} in /workspace.\n{problem_statement}"
        if whether_attach_file else
        f"{problem_statement}"
        # "NOTE: If you want to search something online, please open the browser and use the command 'google_search' first."
    )
    logger.info(f"User request: {user_request}")
    # Run the agent
    raw_answer = await run_single_step(agent, user_request)
    logger.info(f"Raw answer: {raw_answer}")

    format_answer_instructions = "Please summarize your answer with the following template: FINAL ANSWER: [YOUR FINAL ANSWER]. YOUR FINAL ANSWER should be a number OR as few words as possible OR a comma separated list of numbers and/or strings. If you are asked for a number, don't use comma to write your number neither use units such as $ or percent sign unless specified otherwise. If you are asked for a string, don't use articles, neither abbreviations (e.g. for cities), and write the digits in plain text unless specified otherwise. If you are asked for a comma separated list, apply the above rules depending of whether the element to be put in the list is a number or a string."
    logger.info(f"Formatting answer with instructions: {format_answer_instructions}")
    formatted_answer = await run_single_step(agent, format_answer_instructions)
    logger.info(f"Formatted answer: {formatted_answer}")
    reasoning_trace = "\n".join(str(obj) for obj in agent.state.memory_list)
    return formatted_answer, reasoning_trace

def cleanup_docker(instance: dict):
    instance_id = instance.get("task_id", "unknown")
    container_name_filter = f"{instance_id}"
    get_containers_cmd = f"docker ps -aq --filter 'name={container_name_filter}'"
    containers = subprocess.getoutput(get_containers_cmd).strip().split("\n")

    # delete the containers
    if containers and containers[0]:
        delete_containers_cmd = f"docker rm -f {' '.join(containers)}"
        subprocess.run(delete_containers_cmd, shell=True, check=False)
        logger.info(f"🗑️ Deleted containers: {' '.join(containers)}")    

    # delete the workspace
    workspace_folder = os.path.join(os.getcwd(), "gaia_workspace", instance['task_id'])
    if os.path.exists(workspace_folder):
        shutil.rmtree(workspace_folder, ignore_errors=True)
        print(f"🗑️ Deleted folder: {workspace_folder}")

async def main(predictions_file: str = "predictions.jsonl"):
    dataset_path = "gaia_dataset/2023/validation/metadata.parquet"
    dataset = extract_metadata(dataset_path)
    dataset = slice_dataset(dataset, index_start=0, index_end=7)

    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
        future_to_instance = {executor.submit(process_instance, instance): instance for instance in dataset}
        for future in concurrent.futures.as_completed(future_to_instance):
            instance = future_to_instance[future]
            try:
                formatted_answer, reasoning_trace = future.result()
                
                # delete the existing data with the same instance_id
                existing_data = []
                if os.path.exists(predictions_file):
                    with open(predictions_file, "r", encoding="utf-8") as f:
                        for line in f:
                            data = json.loads(line)
                            if data["task_id"] != instance["task_id"]:
                                existing_data.append(data)
                                
                result = {
                    "task_id": instance['task_id'],
                    "model_answer": formatted_answer,
                    "reasoning_trace": reasoning_trace
                }
                
                # append the new result
                existing_data.append(result)
                print(f"Finished instance: {instance['task_id']}")
                with open(predictions_file, "w", encoding="utf-8") as f:
                    for data in existing_data:
                        f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    
            except Exception as e:
                print(f"Error processing instance {instance['task_id']}: {e}")

    print("Saved results to predictions.json")

if __name__ == "__main__":
    asyncio.run(main(predictions_file="predictions.jsonl"))