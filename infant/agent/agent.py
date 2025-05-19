import traceback
from typing import Any, Dict, Optional
from infant.agent.parser import parse
from infant.config import AgentParams
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.computer.computer import Computer
from infant.util.debug import print_messages # For debugging
from infant.agent.state.state import State, AgentState
from infant.agent.memory.memory import ( 
    Task,
    Finish, 
    Memory, 
    Message, 
    TaskFinish, 
    IPythonRun,
    Userrequest,
    Classification, 
)
from infant.config import LitellmParams
from infant.util.logger import infant_logger as logger
from infant.util.backup_image import backup_image_memory
import infant.util.constant as constant
from infant.agent.memory.restore_memory import truncate_output
from infant.util.special_case_handler import handle_planning_repetition, check_accumulated_cost
# from infant.prompt.parse_user_input import parse_user_input_prompt
from infant.prompt.planning_prompt import planning_fake_user_response_prompt
from infant.prompt.tools_prompt import tool_stop, tool_fake_user_response_prompt
from infant.prompt.planning_prompt import (
    planning_task_end_prompt
)
from infant.prompt.execution_prompt import (
    execution_task_end_prompt
)
from infant.agent.memory.retrieve_memory import (
    planning_memory_rtve, 
    classification_memory_rtve,
    execution_memory_rtve
)
from infant.agent.memory.restore_memory import (
    planning_memory_to_diag, 
    classification_memory_to_diag, 
    execution_memory_to_diag,
)
from infant.helper_functions.mouse_click import mouse_click
from infant.helper_functions.file_edit_helper_function import line_drift_correction
from infant.helper_functions.browser_helper_function import convert_web_browse_commands
from infant.agent.memory.file_related_memory import get_diff_patch, git_add_or_not
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, 
                 agent_config: AgentParams, 
                 planning_llm: LLM_API_BASED | None = None,
                 classification_llm: LLM_API_BASED | None = None,
                 execution_llm: LLM_API_BASED | None = None,
                 vg_llm: LLM_OSS_BASED | None = None,
                 fe_llm: LLM_API_BASED | None = None,
                 ap_llm: LLM_API_BASED | None = None,
                 computer: Computer | None = None,
        ) -> None:
        """
        Initializes a new instance of the Agent.

        Parameters:
        - llm (LLM): The llm to be used by this agent
        """
        logger.info(f"Initializing Agent with parameters: agent_config: {agent_config}")
        self.planning_llm = planning_llm
        self.classification_llm = classification_llm
        self.execution_llm = execution_llm
        self.vg_llm = vg_llm
        self.fe_llm = fe_llm
        self.ap_llm = ap_llm
        self.computer = computer
        self.agent_config = agent_config
        self.state = State()
        self.state_updated_event = asyncio.Event()
        self.agent_id = str(id(self))
        
        # FIXME: Move this to the agent config
        self.parse_request = False
        self.critic_execution = False
        self.summarize_execution = False
        
        # prompts
        self.planning_task_end_prompt = planning_task_end_prompt
        self.execution_task_end_prompt = execution_task_end_prompt

    def _active_llms(self):
        """Return a tuple of all non‑None LLM instances owned by the agent."""
        return tuple(
            llm for llm in (
                self.planning_llm,
                self.classification_llm,
                self.execution_llm,
                self.llm,      
            ) if llm is not None
        )

    async def step(self):
        """
        Execute a single step (turn) of the agent's process asynchronously.
        """
        logger.info("Agent step started.")
        while True:
            try:
                # Planning
                await self.planning()
                
                # Determine the task category
                await self.classification()
                
                # Execute the task
                await self.execution()
                
                # upload to git
                git_add_or_not(user_response=True, computer=self.computer)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in agent step: {e}\n{traceback.format_exc()}")
                await self.change_agent_state(new_state=AgentState.ERROR)
            
    async def planning(self,) -> Task:
        while not isinstance(self.state.memory_list[-1], (Task, Finish)):
            messages = await self.memory_to_input("planning", self.state.memory_list)
            # print_messages(messages, 'planning')
            resp, mem_blc= self.planning_llm.completion(messages=messages, stop=['</analysis>', '</task>'])
            if mem_blc:
                self.state.memory_list.extend(mem_blc)
            memory = parse(resp) 
            if isinstance(memory, Message):
                self.state.memory_list.append(memory)
                if self.agent_config.fake_response_mode:
                    planning_fake_user_response = Message(content=planning_fake_user_response_prompt)
                    planning_fake_user_response.source = 'user'
                    self.state.memory_list.append(planning_fake_user_response)
                else:
                    user_response = await asyncio.get_event_loop().run_in_executor(None, input, "Witing for user input:")
                    user_message = Message(content=user_response)
                    user_message.source = 'user'
                    self.state.memory_list.append(user_message)
            else:
                self.state.memory_list.append(memory)
            await asyncio.sleep(0.3)
        if isinstance(self.state.memory_list[-1], Finish):
            await self.change_agent_state(new_state=AgentState.FINISHED)
            
    async def classification(self,) -> Classification:
        messages = await self.memory_to_input("classification", self.state.memory_list)
        # print(f'Messages in classification: {messages}')
        # resp, mem_blc= self.classification_llm.completion(messages=messages, stop=['</clf_task>'])
        # if mem_blc:
        #     self.state.memory_list.extend(mem_blc)
        # Try all prompts
        # resp = '<clf_task>file_edit, code_exec, computer_interaction, web_browse, file_understand</clf_task>'
        resp = '<clf_task>file_edit, file_understand,  code_exec</clf_task>'
        memory = parse(resp) 
        self.state.memory_list.append(memory)

    async def execution(self) -> TaskFinish:
        assert isinstance(self.state.memory_list[-1], Classification)
        cmd_set = self.state.memory_list[-1].cmd_set
        # print(f'cmd_set: {cmd_set}')
        interactive_elements = []
        # if the task is web_browse, we only need to execute the web_browse command
        # if "web_browse" in cmd_set:
        #     # cmd_set = {"web_browse"} # in-place change the cmd_set   
        dropdown_dict = None # FIXME: Do we still need this dropdown?
            
        stop_signals = ['</task_finish>', '</task>', '</execute_ipython>', '</execute_bash>'] # stop signals for the LLM to stop generating
        for cmd in cmd_set:
            if cmd in tool_stop:
                stop_signals.extend(tool_stop[cmd])
        stop_signals = list(set(stop_signals)) # remove duplicates from the stop signals
        
        while not isinstance(self.state.memory_list[-1], TaskFinish):
            messages = await self.memory_to_input("execution", self.state.memory_list, cmd_set = cmd_set)
            # print_messages(messages, 'execution')
            resp, mem_blc= self.execution_llm.completion(messages=messages, stop=stop_signals)
            if mem_blc:
                self.state.memory_list.extend(mem_blc)

            memory = parse(resp)
            if memory.runnable:
                # record the descritpion of the image
                if hasattr(memory, 'code') and memory.code:
                    tmp_code = memory.code
                
                # check if the mouse click is needed FIXME: Move this logic to tools?
                memory, interactive_elements = await mouse_click(self, memory, interactive_elements) # check if the memory is a localization task
                memory = convert_web_browse_commands(memory, dropdown_dict, interactive_elements) # convert the commands to correct format     
                method = getattr(self.computer, memory.action)
                if not memory.result:
                    memory.result = await method(memory)
                    
                # Make sure the edit_file() command is correct
                if isinstance(memory, IPythonRun):
                    if 'edit_file' in memory.code and "Here is the code that you are trying to modified:" in memory.result:
                        result, modified_command = await line_drift_correction(memory, self.computer)
                        logger.info(f"Modified command: {modified_command}")
                        memory.result = result # restore result
                        tmp_code = modified_command # restore code
                        
                # # For web_browser, we need to check the dropdown menu
                # chk_dropdown_result, dropdown_dict = await check_dropdown_options(self, cmd, interactive_elements)
                # memory.result += f'\n{chk_dropdown_result}'  # FIXME: check if this is needed  
                memory.result = truncate_output(output = memory.result)
                
                # convert the coordinate back to image description
                if hasattr(memory, 'code') and memory.code:
                    memory.code = tmp_code
                    
                logger.info(f'Execution Result\n{memory.result}', extra={'msg_type': 'Execution Result'})
                backup_image_memory(memory, constant.MOUNT_PATH)
                self.state.memory_list.append(memory)
            elif isinstance(memory, Message):
                self.state.memory_list.append(memory)
                execution_fake_user_response = Message(content=tool_fake_user_response_prompt)
                execution_fake_user_response.source = 'user'
                self.state.memory_list.append(execution_fake_user_response)
            else:
                self.state.memory_list.append(memory)
            await asyncio.sleep(0.3)
    
    async def change_agent_state(self, new_state: AgentState):
        logger.info(f"Changing agent state to: {new_state}")
        self.state.agent_state = new_state
        self.state_updated_event.set()
        await asyncio.sleep(1)

    async def monitor_agent_state(self):
        while True:
            await self.state_updated_event.wait()
            self.state_updated_event.clear()
            logger.info(f"Agent state updated to: {self.state.agent_state}")
            #if self.state == "completed":
            #    logger.info("Agent reached 'completed' state, stopping monitor")
            #    break
            if self.state.agent_state in ('finished', 'error', 'awaiting_user_input'):
                break
            
    async def memory_to_input(self, case: str, memory_block: list | None = None, *args, **kwargs) -> list[dict]:
        """
        Asynchronously convert the agent's memory to a structured input data format.
        Based on different cases and memory block.

        Args:
        - case (str): The specific case to handle (e.g., planning, classification).
        - memory_block (list): A list of Memory objects to process.

        Returns:
        - list[dict]: The structured input data as a list of messages.
        """
        messages = []

        async def process_memory_block(block, processing_fn):
            """
            Helper function to process a memory block asynchronously.
            Ensures the input is a flat list of Memory objects before processing.
            """
            # Flatten nested lists into a single list
            def flatten(nested):
                for item in nested:
                    if isinstance(item, list):
                        yield from flatten(item)
                    else:
                        yield item
            flat_block = list(flatten(block))
            for item in flat_block:
                if not isinstance(item, (Memory, Userrequest)):
                    raise TypeError(f"Invalid item in memory_block: {item}, type: {type(item)}")

            if asyncio.iscoroutinefunction(processing_fn):
                results = await processing_fn(flat_block)
            else:
                results = processing_fn(flat_block) 
            return results

        if case == "planning":
            memory_block = await process_memory_block(memory_block, planning_memory_rtve)
            messages = planning_memory_to_diag(memory_block, end_prompt=self.planning_task_end_prompt, 
                                                mount_path = self.computer.workspace_mount_path)

        elif case == "classification":
            memory_block = await process_memory_block(memory_block, classification_memory_rtve)
            messages = classification_memory_to_diag(memory_block)

        elif case == "execution":
            cmd_set = kwargs.get('cmd_set', None)
            # print(f'cmd_set in memory_to_input: {cmd_set}')
            memory_block = await process_memory_block(memory_block, execution_memory_rtve)
            messages = execution_memory_to_diag(memory_block, cmd_set, end_prompt=self.execution_task_end_prompt,
                                                mount_path = self.computer.workspace_mount_path)
        return messages

    def extract_image_from_response(self, response: str) -> bytes:
        import base64 
        import re 

        match = re.search(r'data:image/(?P<ext>png|jpeg);base64,(?P<data>.+)', response)
        if match:
            image_data = base64.b64decode(match.group('data'))
            return image_data 
        return b''

    def handle_summary_image(self, image_data: bytes):
        with open('./summary_image.png', 'wb') as f:
            f.write(image_data)
        logger.info("Summary image saved.", extra={'msg_type': 'Summary_Image'})

    async def special_case_handler(self) -> None:
        """
        Handles special cases.
        """
        while True:
            # check if the planning output is repeated
            new_prompt = handle_planning_repetition(self.state.memory_list, 
                                                     max_repetition=self.agent_config.max_planning_iterations)
            if new_prompt:
                self.planning_task_end_prompt = new_prompt
            else:
                self.planning_task_end_prompt = planning_task_end_prompt
            total_cost = sum(
                llm.metrics.accumulated_cost for llm in self._active_llms()
            )
            # check if the accumulated cost exceeds the maximum allowed cost
            if check_accumulated_cost(total_cost, self.agent_config.max_budget_per_task):
                await self.change_agent_state(new_state=AgentState.ERROR)
            await asyncio.sleep(1)