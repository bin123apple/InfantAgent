import sys
import uuid
import asyncio
import traceback
from datetime import datetime
from infant.config import config
from infant.agent.agent import Agent
from infant.computer.computer import Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.agent.memory.memory import Userrequest
from infant.util.logger import infant_logger as logger
from infant.util.save_dataset import save_to_dataset
from infant.agent.memory.memory import Finish, IPythonRun
from infant.prompt.tools_prompt import IMPORTS
import infant.util.constant as constant

async def run_single_step(agent: Agent, user_request_text: str, image = None):
    agent.state.memory_list.append(Userrequest(text=user_request_text, images=image))

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

async def initialize_agent():
    # Initialize the API Based LLM
    litellm_parameter = config.get_litellm_params()
    api_llm = LLM_API_BASED(litellm_parameter)
    
    # Initialize the OSS Based LLM
    if config.use_oss_llm:
        vllm_parameter = config.get_vllm_params()
        oss_llm = LLM_OSS_BASED(vllm_parameter)
    else:
        oss_llm = None

    # Initialize the computer
    computer_parameter = config.get_computer_params()
    sid = str(uuid.uuid4())
    computer = Computer(computer_parameter, sid = sid)
    
    # cd to the workspace/clear the workspace/activate conda
    exit_code, output = computer.execute(f'cd /workspace && rm -rf *')
    if exit_code != 0:
        logger.error(f'Failed to clear the workspace directory: {output}')
        sys.exit(1)
    else:
        logger.info("Workspace directory has been cleared successfully.")
    
    # activate conda
    exit_code, output = computer.execute(f'source /infant/miniforge3/etc/profile.d/conda.sh')
    exit_code, output = computer.execute('export PATH=/infant/miniforge3/bin:$PATH')
    exit_code, output = computer.execute(f'source ~/.bashrc')
    logger.info(f'Conda environment activated successfully.')

    # git initial commit 
    exit_code, output = computer.execute(f'git init') # initialize git
    exit_code, output = computer.execute('git config --global core.pager ""')
    exit_code, output = computer.execute(f'git add .') # initial add
    exit_code, output = computer.execute(f'git commit -m "base commit"') # initial add
    logger.info(f'Git initialized successfully.')
    
    # Initialize the Agent
    agent_parameter = config.get_agent_params()
    agent = Agent(agent_parameter, api_llm, oss_llm, computer)
    logger.info(f'Agent initialized successfully.')
    exit_code, output = computer.execute(f'cd /workspace && rm -rf *')
    
    # imports
    import_memory = IPythonRun(code = IMPORTS)
    await computer.run_ipython(import_memory)
    return agent, computer

async def main():
    
    try:
        # Initialize the agent
        agent, computer = await initialize_agent()
        constant.MOUNT_PATH = computer.workspace_mount_path

        # Run the agent
        while True:
            try:
                exit_code, output = computer.execute(f'pwd')
                logger.info(f'Current working directory: {output}')
                user_request = input("Input your request or use type exit to refresh the agent: ")
                if user_request.lower() == 'exit':
                    agent.state.reset()
                    exit_code, output = computer.execute(f'cd /workspace && rm -rf *')
                    logger.info("Agent state reset.")
                    user_request = input("Input your new request: ")
                await run_single_step(agent, user_request)
            except KeyboardInterrupt:
                logger.warning("exit")
                break
            except Exception as e:
                error_details = traceback.format_exc()
                logger.error(f'Error in main: {e}\nTraceback:\n{error_details}')
                break
    
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f'Error in main: {e}\nTraceback:\n{error_details}')
    except KeyboardInterrupt:
        logger.warning('KeyboardInterrupt in main')
    finally:
        await cleanup(agent=agent, computer=computer)

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


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
