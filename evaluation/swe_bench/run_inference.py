import re
import os
import ast
import uuid
import yaml
import json
import shutil
import asyncio
import tempfile
import traceback
import subprocess
from datetime import datetime
import concurrent.futures
from infant.config import config, ComputerParams
from datasets import load_dataset
from infant.agent.agent import Agent
from infant.computer.computer import Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.agent.memory.restore_memory import truncate_output
from infant.util.logger import infant_logger as logger
from infant.util.save_dataset import save_to_dataset
from infant.agent.memory.memory import Userrequest, Finish, IPythonRun
from infant.util.logger import reset_logger_for_multiprocessing, LOG_DIR
from infant.prompt.tools_prompt import IMPORTS

MAX_FEEDBACK_TIME = 1
MAX_CHECK_TIME = 1

def check_missing_instance_ids(original_instance_ids, predictions_file):
    valid_instance_ids = []
    
    if not os.path.exists(predictions_file):
        print(f"File {predictions_file} does not exist.")
        return [], original_instance_ids

    with open(predictions_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Fail to parse on line, error {e}")
                continue
            if data.get("model_patch", "") != "":
                valid_instance_ids.append(data.get("instance_id"))
    
    missing_ids = [instance_id for instance_id in original_instance_ids if instance_id not in valid_instance_ids]
    
    return valid_instance_ids, missing_ids

def check_feedback_logs(original_instance_ids, error_message):
    logs_dir = os.path.abspath(os.path.join(os.getcwd(), "../../logs"))
    error_instance_ids = []
    
    for instance_id in original_instance_ids:
        log_file_path = os.path.join(logs_dir, f"{instance_id}.log")
        if os.path.exists(log_file_path):
            with open(log_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if error_message in content:
                    error_instance_ids.append(instance_id)
        else:
            print(f"log file {log_file_path} does not exist.")
    
    return error_instance_ids

def extract_failed_tests(pytest_output):
    """
    Parse the pytest output to extract failed tests and their error messages.
    """
    failed_tests = []

    failure_section_match = re.search(r"=+\s*FAILURES\s*=+\n(.*?)\n=+", pytest_output, re.DOTALL)
    if failure_section_match:
        failure_section = failure_section_match.group(1)
        failures = re.split(r"\n_{5,}", failure_section)
        for failure in failures:
            match = re.search(r"(test_[^\s]+)", failure)
            if match:
                test_name = match.group(1)
                error_message = failure.strip()
                failed_tests.append({
                    "test_name": test_name,
                    "error_message": error_message
                })

    return failed_tests

def get_instance_docker_image(instance_id: str) -> str:
    '''
    Use test bed from Openhands (https://github.com/All-Hands-AI/OpenHands/blob/main/evaluation/benchmarks/swe_bench/run_infer.py)
    '''
    DOCKER_IMAGE_PREFIX = os.environ.get('EVAL_DOCKER_IMAGE_PREFIX', 'docker.io/xingyaoww/')
    image_name = 'sweb.eval.x86_64.' + instance_id
    image_name = image_name.replace(
        '__', '_s_'
    )  # to comply with docker image naming convention
    return (DOCKER_IMAGE_PREFIX.rstrip('/') + '/' + image_name).lower()

async def initialize_docker_agent(instance: dict, config=config)-> Agent:
    # Initialize the API Based LLM
    litellm_parameter = config.get_litellm_params()
    litellm_parameter.model = 'o3-mini'
    # litellm_parameter.base_url = 'https://api.deepseek.com/v1'
    litellm_parameter.api_key = os.environ.get('OPENAI_API_KEY', '')
    # litellm_parameter.model = 'claude-3-7-sonnet-20250219'
    # litellm_parameter.gift_key = True
    api_llm = LLM_API_BASED(litellm_parameter)

    reason_litellm_parameter = config.get_litellm_params()
    reason_litellm_parameter.model = 'claude-3-7-sonnet-20250219'
    reason_litellm_parameter.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    reasoning_llm = LLM_API_BASED(reason_litellm_parameter)

    execution_litellm_parameter = config.get_litellm_params()
    execution_litellm_parameter.model = 'claude-3-7-sonnet-20250219'
    # execution_litellm_parameter.base_url = 'https://api.deepseek.com/v1'
    execution_litellm_parameter.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    execution_llm = LLM_API_BASED(execution_litellm_parameter)    

    # Initialize the OSS Based LLM
    if config.use_oss_llm:
        vllm_parameter = config.get_vllm_params()
        oss_llm = LLM_OSS_BASED(vllm_parameter)
    else:
        oss_llm = None
    logger.info(f'LLMs initialized successfully.')

    # build the docker
    instance_id = instance.get("instance_id", "unknown")
    instance_base_image = get_instance_docker_image(instance_id)
    new_instance_image = f"{instance_id}-gnome"
    logger.info(f"🔨 Building new Docker image: {new_instance_image}")
    build_command = f"docker build --build-arg BASE_IMAGE={instance_base_image} -t {new_instance_image} ."
    subprocess.run(build_command, shell=True, check=True)

    # initialize the computer
    computer_parameter: ComputerParams = config.get_computer_params()
    computer_parameter.computer_container_image = new_instance_image
    computer_parameter.instance_id = instance_id
    computer_parameter.gui_port = None
    computer_parameter.consistant_computer = None
    computer_parameter.ssh_bind_port = None
    computer_parameter.nomachine_bind_port = None
    computer_parameter.run_as_infant = True
    computer_parameter.text_only_docker = True
    workspace_path = os.path.join(os.getcwd(), "swe_repos", instance_id, "workspace")
    os.makedirs(workspace_path, exist_ok=True)
    computer_parameter.workspace_mount_path = workspace_path

    sid = str(uuid.uuid4())
    try:
        computer = Computer(computer_parameter, sid = sid)
    except:
        logger.error({traceback.format_exc()})
        
    computer.execute('mkdir -p /swe_util/eval_data/instances')
    swe_instance_json_name = 'swe-bench-instance.json'
    with tempfile.TemporaryDirectory() as temp_dir:
        # Construct the full path for the desired file name within the temporary directory
        temp_file_path = os.path.join(temp_dir, swe_instance_json_name)
        # Write to the file with the desired name within the temporary directory
        with open(temp_file_path, 'w') as f:
            json.dump([instance], f)
        computer.copy_to(temp_file_path, '/swe_util/eval_data/instances/')
    computer.copy_to(
        str(os.path.join(os.path.dirname(__file__), 'instance_swe_entry.sh')),
        '/swe_util/',
    )
    
    computer.execute(f"""echo 'export SWE_INSTANCE_ID={instance_id}' >> ~/.bashrc && echo 'export PIP_CACHE_DIR=~/.cache/pip' >> ~/.bashrc && echo "alias git='git --no-pager'" >> ~/.bashrc""")
    computer.execute('export USER=$(whoami)')
    computer.execute('echo USER=${USER}')
    exit_code, output = computer.execute('cat ~/.bashrc')
    logger.info(f'~/.bashrc: {output}')
    computer.execute('source ~/.bashrc')
    logger.info(f'finished sourcing ~/.bashrc')
    computer.execute('source /swe_util/instance_swe_entry.sh')
    logger.info('Finishd source /swe_util/instance_swe_entry.sh')
    # Activate instance-specific environment
    computer.execute('export PATH=/opt/miniconda3/envs/testbed/bin:$PATH')
    computer.execute('source ~/.bashrc')
    exit_code, output = computer.execute('which python')
    print(f"Python path: {output}")
    logger.info('computer initialized successfully.')
    
    # Initialize the Agent
    agent_parameter = config.get_agent_params()
    agent_parameter.fake_response_mode = True
    agent_parameter.max_budget_per_task = 10
    agent = Agent(agent_parameter, api_llm, reasoning_llm, 
                  api_llm, execution_llm, oss_llm, computer)
    logger.info(f'Agent initialized successfully.')
    
    import_memory = IPythonRun(code = IMPORTS)
    await computer.run_ipython(import_memory)
    
    return agent

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

def unit_test(agent: Agent, instance: dict):
    original_unit_test_file = ast.literal_eval(instance.get("PASS_TO_PASS", "unknown")) + ast.literal_eval(instance.get("FAIL_TO_PASS", "unknown"))
    test_files = set() 
    if 'django/django' in instance['repo']:
        for test in original_unit_test_file:
            try:
                test_parts = test.split(" (")
                if len(test_parts) == 2:
                    test_method = test_parts[0]
                    test_class_info = test_parts[1].rstrip(")")
                    test_folder = test_class_info.split(".")[0] + '.' + test_class_info.split(".")[1]
                    full_test_path = f"{test_folder}"
                    test_files.add(full_test_path)
            except Exception as e:
                print(f"Error parsing test: {test} - {e}")
    elif 'sympy/sympy' in instance['repo']:
        exit_code, output = agent.computer.execute(f"pip install pytest")
        exit_code, output = agent.computer.execute(f"pip install py")
        for test in original_unit_test_file:
            test_files.add(test)
    else:
        for test in original_unit_test_file:
            file_path = test.split("::")[0]
            test_files.add(file_path)
    failed_tests_info = []
    logger.info(f"Running unit tests on {test_files}...")
    all_tests = ''
    for test_file in test_files:
        exit_code, output = agent.computer.execute(f"cd {agent.computer.workspace_git_path}")
        if 'django/django' in instance['repo']:
            test_folder = "/".join(test_file.split("."))
            test_file_path = f"tests/{test_folder}.py"
            test_dir_path = f"tests/{test_folder}"

            check_file_cmd = f"test -f {test_file_path} && echo 'FILE EXISTS' || echo 'FILE NOT FOUND'"
            check_dir_cmd = f"test -d {test_dir_path} && echo 'DIR EXISTS' || echo 'DIR NOT FOUND'"

            output = ''
            file_exit_code, file_output = agent.computer.execute(check_file_cmd)
            output += file_output
            dir_exit_code, dir_output = agent.computer.execute(check_dir_cmd)
            output += dir_output

            if "EXISTS" in output:
                all_tests += f"{test_file} "
                exit_code, output = agent.computer.execute(f"python tests/runtests.py {all_tests.strip()}")
            else:
                exit_code = 0
                output = "Folder or file does not exist"
        elif 'sympy/sympy' in instance['repo']:
            exit_code, output = agent.computer.execute(f"pytest -k {test_file}", timeout=300)
        elif 'psf/requests' in instance['repo']:
            exit_code = 0
        else:
            exit_code, output = agent.computer.execute(f"pytest {test_file} --rootdir={agent.computer.workspace_git_path} --disable-warnings -v")
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)
        logger.info(f"Unit test result for {test_file}: {output}")
        failed_tests_info.append(output)
        
    if exit_code != 0:
        error_detail = ''
        for output in failed_tests_info:
            error_detail += output
        return False, error_detail, test_files
    else:
        return True, None, test_files

async def run_single_instance(instance: dict, logger):
    # Initialize the docker and the Agent
    agent = await initialize_docker_agent(instance=instance, config=config)
    
    # prepare the repo
    instance_id: str = instance.get("instance_id", "unknown")
    base_commit: str = instance.get("base_commit", "unknown")
    id = instance_id.split("-")[-1]
    version = instance.get("version", "unknown")
    folder = instance_id.replace(f'-{id}', f'__{version}')
    logger.info(f"Running instance: {instance_id}")
    agent.computer.workspace_git_path = f'/workspace/{folder}'
    
    # Step 1. initial instruction:
    problem_statement: str = instance.get("problem_statement", "unknown")
    logger.info(f"Problem statement:\n{problem_statement}")
    initial_user_request_text = (
        f"I've uploaded a python code repository in the directory /workspace/{folder}. Consider the following issue description:\n"
        "<issue_description>\n"
        f"{problem_statement}\n"
        "</issue_description>\n"
        "Please help to:"
        "1. EXPLORATION: First, thoroughly explore the repository structure using tools like `find` and `grep`.\n"
        "- Identify all files mentioned in the problem statement.\n"
        "- Locate where the issue occurs in the codebase.\n"
        "- Understand the surrounding context and dependencies.\n"
        "- Use `grep` to search for relevant functions, classes, or error messages\n"
        "Fow now, you don't need to fix this issue, you only need to explore the repository and provide a summary of your findings."
    )
    exploration_response = await run_single_step(agent, initial_user_request_text)
    logger.info(f"Exploration response: {exploration_response}")
    
    # Step 2. Analysis the bug:
    analysis_user_request_text = (
        "Let's move on to the next step:\n"
        f"2. ANALYSIS: Based on your exploration, think carefully about the problem and propose 2-5 possible approaches to fix the issue.\n"
        "- Analyze the root cause of the problem\n"
        "- Select the most promising approach and explain your reasoning"
        "**For now, you don't need to fix this issue, you only need to analyze the bug and provide a summary of your findings.**"
    )
    analysis_response = await run_single_step(agent, analysis_user_request_text)
    logger.info(f"Analysis response: {analysis_response}")
    
    # Step 3. Reproduce the bug:
    analysis_user_request_text = (
        "Let's move on to the next step:\n"
        f"3. TEST CREATION: Before implementing any fix, create a script to reproduce and verify the issue.\n"
        "- Look at existing test files in the repository to understand the test format/structure\n"
        "- Create a minimal reproduction script that demonstrates the issue\n"
        "- Run your script to confirm the error exists"
        "**For now, you don't need to fix this issue, you only need to create a script and run it to reproduce the issue.**"
    )
    analysis_response = await run_single_step(agent, analysis_user_request_text)
    logger.info(f"Analysis response: {analysis_response}")    
    # # agent.state.reset()
    # get_new_files_cmd = f'bash -c "git -C {agent.computer.workspace_git_path} diff --name-only --diff-filter=A {base_commit} HEAD > /workspace/new_files.txt"'
    # logger.info(f"Executing command to get new files: {get_new_files_cmd}")
    # agent.computer.execute(get_new_files_cmd)
    # exit_code, output =  agent.computer.execute('cat /workspace/new_files.txt')
    # logger.info(f"New files: {output}")
    
    # Step 4. Try to fix the bug:
    implementation_request_text = (
        f"Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n"
        "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n" 
        "Also the development Python environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
        f"Your task is to make the minimal changes to non-test files in the /workspace/{folder} directory to ensure the <issue_description> is satisfied.\n"
        "Follow these steps to resolve the issue:\n"
        "4. IMPLEMENTATION: Edit the source code to implement your chosen solution.\n"
        " - Make minimal, focused changes to fix the issue"
    )
    implementation_response = await run_single_step(agent, implementation_request_text)
    logger.info(f"Implementation response: {implementation_response}")
    
    # Step 5. Verification:
    verification_request_text = ( 
        "5. VERIFICATION: Test your implementation thoroughly.\n"
        "- Run your reproduction script to verify the fix works\n"
        "- Add edge cases to your test script to ensure comprehensive coverage\n"
        "- Run existing tests related to the modified code to ensure you haven't broken anything"
    )
    final_answer = await run_single_step(agent, verification_request_text)
    logger.info(f"Verification response: {final_answer}")
    
    # Step 6. unit test with feedback:
    feedback_time = 0
    unit_test_result = False
    while not unit_test_result:
        if feedback_time > MAX_FEEDBACK_TIME:
            logger.info("Feedback time exceeded, stopping the process.")
            break
        
        # Step 6. unit test:
        unit_test_result, error_detail, test_files = unit_test(agent, instance)
        test_file_names = ''
        for test_file in test_files:
            test_file_names += test_file + ' '
        if unit_test_result:
            break
        else:
            if error_detail:
                error_detail = truncate_output(error_detail, max_chars = 4_000)
            logger.info(f"Unit test failed with error: {error_detail}")
            feedback_message = (
                f'Your modifications have caused some unit test code to fail, with the following error message:\n'
                f'{error_detail}\n'
                f'Please review the error message and continue making modifications based on the error message.\n' 
                f'NOTE: You should NOT modify the code in {test_file_names}. Those are the unit test files.\n'
                'Please help me to make sure that the unit tests pass.'
                'Once you have completed the changes, I will run the unit tests again.'
            )
            final_answer = await run_single_step(agent, feedback_message)
        
        feedback_time += 1
    
    # extract git patch:
    exit_code, modified_files = agent.computer.execute(
        f"git diff --no-color {base_commit} HEAD --diff-filter=M --name-only"
    )
    logger.info(f"Modified files:\n{modified_files}")

    if modified_files.strip():
        exit_code, git_diff = agent.computer.execute(
            f"git diff --no-color {base_commit} HEAD -- {' '.join(modified_files.splitlines())}"
        )
    else:
        git_diff = ""

    logger.info(f"Git diff:\n{git_diff}")  
    
    # remove the lines before the first "diff --git"
    if "diff --git" in git_diff:
        lines = git_diff.splitlines() 
        index = next((i for i, line in enumerate(lines) if "diff --git" in line), None)  
        if index is not None:
            git_diff = "\n".join(lines[index:]) 


    return git_diff, final_answer

async def cleanup(agent: None | Agent = None, computer: None | Computer = None):
    
    # Handle the screenshots
    screenshots_dir = "/workspace/screenshots/"
    end_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_folder = f"/workspace/log_{end_time}_screenshots"

    exit_code, output = computer.execute(f'[ -d {screenshots_dir} ] && mv {screenshots_dir} {log_folder}')
    if exit_code == 0:
        logger.info(f"Screenshots moved successfully to: {log_folder}")
    else:
        logger.warning(f"Failed to move screenshots. Directory might not exist. Output: {output}")
        
    # record the log to dataset
    if config.feedback_mode and exit_code == 0:
        mount_path = config.workspace_mount_path
        image_data_path = log_folder.replace("/workspace", mount_path, 1)
        save_to_dataset(agent.state.memory_list, image_data_path)

def cleanup_docker(instance: dict):
    instance_id = instance.get("instance_id", "unknown")
    new_instance_image: str = f"{instance_id}-gnome"
    get_containers_cmd = f"docker ps -aq --filter ancestor={new_instance_image}"
    containers = subprocess.getoutput(get_containers_cmd).strip().split("\n")

    # delete the containers
    if containers and containers[0]:
        delete_containers_cmd = f"docker rm -f {' '.join(containers)}"
        subprocess.run(delete_containers_cmd, shell=True, check=False)
        logger.info(f"🗑️ Deleted containers: {' '.join(containers)}")    

    # delete the workspace
    repo_folder = f"swe_repos/{instance_id}"
    if os.path.exists(repo_folder):
        shutil.rmtree(repo_folder, ignore_errors=True)
        print(f"🗑️ Deleted folder: {repo_folder}")
      
def process_instance(instance: dict):
    instance_id = instance['instance_id']

    reset_logger_for_multiprocessing(logger, instance_id, LOG_DIR)

    try:
        git_diff, final_answer = asyncio.run(run_single_instance(instance, logger))
        logger.info("Finish processing instance: %s", instance_id)
        cleanup_docker(instance)
        logger.info("Cleanup docker successfully")
    except Exception as e:
        logger.exception("Fail to process instance %s Error: %s", instance_id, e)
        cleanup_docker(instance)
        logger.info("Cleanup docker successfully")
        raise e

    return git_diff, final_answer

def filter_dataset(dataset, start_idx=None, end_idx=None, limit=None, instance_ids=None):
    """
    Filters the dataset based on index range, limit, and/or specific instance_ids.

    Args:
        dataset: The dataset to filter.
        start_idx (int, optional): Start index of the dataset to include.
        end_idx (int, optional): End index of the dataset to include.
        limit (int, optional): Limit the number of rows returned.
        instance_ids (list[str], optional): A list of instance_id values to include.

    Returns:
        Filtered dataset.
    """
    if instance_ids is not None:
        dataset = dataset.filter(lambda x: x["instance_id"] in instance_ids)
    else:
        num_rows = len(dataset)
        start_idx = 0 if start_idx is None else max(0, start_idx)
        end_idx = num_rows if end_idx is None else min(num_rows, end_idx)
        dataset = dataset.select(range(start_idx, end_idx))
        if limit is not None:
            dataset = dataset.select(range(min(limit, len(dataset))))
    
    return dataset


def one_turn(predictions_file, instance_ids):
    dataset = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    start_idx = None
    end_idx = None
    dataset = filter_dataset(dataset, start_idx=start_idx, end_idx=end_idx, limit=None, instance_ids=instance_ids)

    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        future_to_instance = {executor.submit(process_instance, instance): instance for instance in dataset}
        for future in concurrent.futures.as_completed(future_to_instance):
            instance = future_to_instance[future]
            try:
                git_diff, final_answer = future.result()
                
                # delete the existing data with the same instance_id
                existing_data = []
                if os.path.exists(predictions_file):
                    with open(predictions_file, "r", encoding="utf-8") as f:
                        for line in f:
                            data = json.loads(line)
                            if data["instance_id"] != instance["instance_id"]:
                                existing_data.append(data)
                                
                result = {
                    "instance_id": instance['instance_id'],
                    "model_name_or_path": "Claude_3.7_Sonnet_Reason_gpt_4o_Execute",
                    "final_answer": final_answer,
                    "model_patch": git_diff,
                }
                
                # append the new result
                existing_data.append(result)
                print(f"Finished instance: {instance['instance_id']}")
                with open(predictions_file, "w", encoding="utf-8") as f:
                    for data in existing_data:
                        f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    
            except Exception as e:
                print(f"Error processing instance {instance['instance_id']}: {e}")

    print(f"Saved results to {predictions_file}")
    
def main(predictions_file, instance_ids):
    """
    Main function to run the one_turn function.
    This function can be modified to handle command line arguments or other configurations if needed.
    """
    try:
        check_time = 0
        while True:
            one_turn(predictions_file, instance_ids)
            logger.info(f"{check_time + 1} turn completed.")
            check_time += 1
            if check_time >= MAX_CHECK_TIME:
                logger.info("Maximum feedback time reached, stopping the process.")
                break
            # check if there is a patch
            valid_instance_ids, missing_ids = check_missing_instance_ids(instance_ids, predictions_file)
            
            # check if there are any feedback logs indicating failure
            error_ids = check_feedback_logs(instance_ids, error_message="Feedback time exceeded, stopping the process.")
            
            instance_ids = list(set(missing_ids) | set(error_ids))
            logs_dir = os.path.abspath(os.path.join(os.getcwd(), "../../logs"))
            for inst_id in instance_ids:
                log_file = os.path.join(logs_dir, f"{inst_id}.log")
                if os.path.exists(log_file):
                    os.remove(log_file)
                    print(f"Deleted log file: {log_file}")
                else:
                    print(f"Log file {log_file} does not exist, cannot delete.")
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    instance_ids = [
  "django__django-11451",
  "django__django-11603",
  "django__django-12858",
  "django__django-13417",
  "django__django-14500",
  "django__django-15930",
  "django__django-16032",
  "django__django-16256",
  "matplotlib__matplotlib-20859",
  "matplotlib__matplotlib-22719",
  "matplotlib__matplotlib-24970",
  "matplotlib__matplotlib-25122",
  "mwaskom__seaborn-3069",
  "psf__requests-1766",
  "psf__requests-1921",
  "psf__requests-5414",
  "pydata__xarray-4075",
  "pydata__xarray-6599",
  "pydata__xarray-6744",
  "pydata__xarray-6938",
  "pylint-dev__pylint-4661",
  "pylint-dev__pylint-6386",
  "pylint-dev__pylint-6528",
  "pytest-dev__pytest-10081",
  "pytest-dev__pytest-7432",
  "scikit-learn__scikit-learn-10297",
  "scikit-learn__scikit-learn-12585",
  "scikit-learn__scikit-learn-12973",
  "scikit-learn__scikit-learn-13135",
  "sphinx-doc__sphinx-11445",
  "sphinx-doc__sphinx-7454",
  "sphinx-doc__sphinx-8551",
  "sympy__sympy-13798",
  "sympy__sympy-14531",
  "sympy__sympy-16792",
  "sympy__sympy-17630"
]

    main(predictions_file = "predictions.jsonl", instance_ids = instance_ids)