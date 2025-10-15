import sys
import uuid
import asyncio
import traceback
from datetime import datetime
from infant.agent.agent import Agent
from infant.config import Config, config
from infant.computer.computer import Computer as Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.agent.memory.memory import Userrequest
from infant.util.logger import infant_logger as logger
from infant.util.save_dataset import save_to_dataset
from infant.agent.memory.memory import Finish, IPythonRun
from infant.prompt.tools_prompt import IMPORTS
import infant.util.constant as constant
import os 
from pathlib import Path

async def run_single_step(agent: Agent, user_request_text: str, image = None):
    agent.state.memory_list.append(Userrequest(text=user_request_text, images=image))
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

async def initialize_agent(config: Config = None):
    if config is None:
        config = Config()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = Path(current_dir).resolve().parent
        CONFIG_FILE = root_dir / "config.toml"
        user_config = config._load()
        config.__dict__.update(user_config)
        config.finalize_config()

    # Initialize variables to None for error handling
    computer = None
    agent = None

    # Initialize the API Based LLM
    plan_parameter = config.get_litellm_params(overrides = config.planning_llm)
    planning_llm = LLM_API_BASED(plan_parameter)
    classification_parameter = config.get_litellm_params(overrides = config.classification_llm)
    classification_llm = LLM_API_BASED(classification_parameter)
    execution_parameter = config.get_litellm_params(overrides = config.execution_llm)
    execution_llm = LLM_API_BASED(execution_parameter)
    vg_parameter = config.get_vllm_params(overrides = config.vg_llm)
    vg_llm = LLM_OSS_BASED(vg_parameter)
    fe_parameter = config.get_litellm_params(overrides = config.fe_llm)
    fe_llm = LLM_API_BASED(fe_parameter)
    tm_parameter = config.get_litellm_params(overrides = config.tm_llm)
    tm_llm = LLM_API_BASED(tm_parameter)
    ap_parameter = config.get_litellm_params(overrides = config.ap_llm)
    ap_llm = LLM_API_BASED(ap_parameter)
     
    # Initialize the computer using SSH-based connection
    # When running from within the infant-agent container, connect to computer-container
    # via the docker network using the container name as hostname
    computer_parameter = config.get_computer_params()

    # Create Computer instance
    # Connect to 'infant-computer' (container name) on port 22 within docker network
    computer = Computer(
        ssh_hostname='infant-computer',  # Docker network container name
        ssh_port=22,  # Internal container port (not the mapped host port)
        ssh_password=computer_parameter.ssh_password or '123',
        ssh_username='infant' if computer_parameter.run_as_infant else 'root',
        ssh_root_password='123',  # Root password for setup
        timeout=computer_parameter.computer_timeout or 120,
        workspace_dir=computer_parameter.workspace_mount_path_in_computer or '/workspace',
        enable_auto_lint=False,  # Set to True to enable auto-linting
        initialize_plugins=True,  # Initialize plugins and tools
    )

    # Set the workspace mount path for constant
    constant.MOUNT_PATH = config.workspace_mount_path

    # cd to the workspace/clear the workspace/activate conda
    # Use sudo to handle permission issues, or change ownership first
    exit_code, output = computer.execute(f'cd /workspace && sudo rm -rf * 2>/dev/null || rm -rf *')
    if exit_code != 0:
        logger.warning(f'Failed to clear some files in workspace directory: {output}')
        # Try changing ownership and removing again
        exit_code, output = computer.execute(f'cd /workspace && sudo chown -R {computer.ssh_username}:{computer.ssh_username} . && rm -rf *')
        if exit_code != 0:
            logger.error(f'Failed to clear the workspace directory after changing ownership: {output}')
        else:
            logger.info("Workspace directory has been cleared successfully (after ownership change).")
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
    agent = Agent(agent_config = agent_parameter, planning_llm = planning_llm,
                  classification_llm = classification_llm, execution_llm = execution_llm,
                  vg_llm = vg_llm, fe_llm = fe_llm, tm_llm = tm_llm, ap_llm = ap_llm, computer = computer)
    logger.info(f'Agent initialized successfully.')
    exit_code, output = computer.execute(f'cd /workspace && rm -rf *')
    
    # imports
    import_memory = IPythonRun(code = IMPORTS)
    await computer.run_ipython(import_memory)

    import_memory = IPythonRun(code = "press_key('Escape')")
    await computer.run_ipython(import_memory)
    return agent, computer

    # Note: If an exception occurs during initialization, agent and/or computer may be None
    # The calling function should handle this appropriately


async def main():
    # Initialize variables to None for error handling
    agent = None
    computer = None

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
                    # reset state
                    agent.state.reset()

                    # reset accumulated cost
                    for llm in agent._active_llms():
                        llm.metrics.accumulated_cost = 0

                    # clean workspace
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
    # Check if computer is available
    if computer is None:
        logger.warning("Computer not initialized, skipping cleanup")
        return

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


def cli_entry():
    """Entry point for the CLI command."""
    asyncio.run(main())

# Run the main function
if __name__ == "__main__":
    cli_entry()
