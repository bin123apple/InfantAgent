import re
import os
import sys
import uuid
import time
import json
import shutil
import asyncio
import tempfile
import mimetypes
import traceback
import subprocess
from typing import Tuple
import concurrent.futures
from datetime import datetime
from infant.config import config, ComputerParams
from datasets import load_dataset
from infant.agent.agent import Agent
from infant.computer.computer import Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.agent.memory.memory import Userrequest, Finish, IPythonRun
from infant.util.logger import infant_logger as logger
from infant.util.save_dataset import save_to_dataset
from infant.util.logger import reset_logger_for_multiprocessing, LOG_DIR
from infant.prompt.tools_prompt import IMPORTS
import infant.util.constant as constant

def extract_metadata(filename):
    records = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Line: {line}")
                continue
    return records

async def initialize_docker_agent(instance: dict, config=config)-> Agent:
    global MOUNT_PATH
    # Initialize the API Based LLM
    litellm_parameter = config.get_litellm_params()
    litellm_parameter.gift_key = False
    api_llm = LLM_API_BASED(litellm_parameter)
    
    # Initialize the OSS Based LLM
    if config.use_oss_llm:
        vllm_parameter = config.get_vllm_params()
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
    
    # Initialize the Agent
    agent_parameter = config.get_agent_params()
    agent_parameter.fake_response_mode = True
    agent_parameter.max_budget_per_task = 10
    agent = Agent(agent_parameter, api_llm, oss_llm, computer)
    logger.info(f'Agent initialized successfully.')
    
    import_memory = IPythonRun(code = IMPORTS)
    await computer.run_ipython(import_memory)
    
    import_memory = IPythonRun(code = "press_key('Escape')")
    await computer.run_ipython(import_memory)
    
    # set up initial workspace
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
    # Intialize the docker and the Agent
    agent = await initialize_docker_agent(instance=instance, config=config)
    # time.sleep(1000000000)
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
        f"{problem_statement}\n"
        "NOTE: If you want to search something online, please and the browser and use the command 'google_search' first. "
        "If you still can not find the answer, you can navigate to the corresponding website and "
        "try to find more details. "
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
    dataset_path = "gaia_dataset/2023/validation/metadata_test.jsonl"
    dataset = extract_metadata(dataset_path)
    
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