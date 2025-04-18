import re
import os
import sys
import uuid
import time
import json
import shutil
import asyncio
import traceback
import subprocess
from typing import List, Dict, Any
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

def extract_metadata(filename: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with open(filename, 'r', encoding='utf-8') as f:
        test_all_meta: Dict[str, List[str]] = json.load(f)

    for domain, example_ids in test_all_meta.items():
        for example_id in example_ids:
            config_file = os.path.join("examples", domain, f"{example_id}.json")
            with open(config_file, 'r', encoding='utf-8') as cf:
                example = json.load(cf)
            records.append(example)

    return records

async def initialize_docker_agent(instance: dict, config=config)-> Agent:
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
    computer_parameter.instance_id = instance['id']
    computer_parameter.workspace_mount_path = os.path.join(os.getcwd(), "osworld_workspace", instance['id'])
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
    agent = Agent(agent_parameter, api_llm, oss_llm, computer)
    logger.info(f'Agent initialized successfully.')
    
    import_memory = IPythonRun(code = IMPORTS)
    await computer.run_ipython(import_memory)
    
    import_memory = IPythonRun(code = "press_key('Escape')")
    await computer.run_ipython(import_memory)
    
    # set up initial workspace
    computer.execute(f'sudo DEBIAN_FRONTEND=noninteractive apt remove -s -y gnome-keyring')
    
    task_pre_config = instance.get("task_config", {})
    for cfg in task_pre_config:
        config_type: str = cfg["type"]
        parameters: Dict[str, Any] = cfg["parameters"]
        setup_function: str = "_{:}_setup".format(config_type)
        assert hasattr(computer, setup_function), f'Setup controller cannot find init function {setup_function}'
        getattr(computer, setup_function)(**parameters)
        logger.info("SETUP: %s(%s)", setup_function, str(parameters))
    
    # set up the initial state
    
    
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
    task_id: str = instance.get("id", "unknown")
    logger.info(f"Running instance: {task_id}")

    # prepare the user request text/files
    instruction: str = instance.get("instruction", "unknown")
    logger.info(f"User request: {instruction}")
    # Run the agent
    answer = await run_single_step(agent, instruction)
    logger.info(f"Answer: {answer}")
    reasoning_trace = "\n".join(str(obj) for obj in agent.state.memory_list)
    return answer, reasoning_trace

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
    dataset_path = "evaluation_examples/test_all.json"
    dataset = extract_metadata(dataset_path)

    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        future_to_instance = {executor.submit(process_instance, instance): instance for instance in dataset}
        for future in concurrent.futures.as_completed(future_to_instance):
            instance = future_to_instance[future]
            try:
                answer, reasoning_trace = future.result()
                
                # delete the existing data with the same instance_id
                existing_data = []
                if os.path.exists(predictions_file):
                    with open(predictions_file, "r", encoding="utf-8") as f:
                        for line in f:
                            data = json.loads(line)
                            if data["task_id"] != instance["id"]:
                                existing_data.append(data)
                                
                result = {
                    "task_id": instance['id'],
                    "model_answer": answer,
                    "reasoning_trace": reasoning_trace
                }
                
                # append the new result
                existing_data.append(result)
                print(f"Finished instance: {instance['id']}")
                with open(predictions_file, "w", encoding="utf-8") as f:
                    for data in existing_data:
                        f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    
            except Exception as e:
                print(f"Error processing instance {instance['id']}: {e}")

    print("Saved results to predictions.json")

if __name__ == "__main__":
    asyncio.run(main(predictions_file="predictions.jsonl"))