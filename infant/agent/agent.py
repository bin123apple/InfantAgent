import re
import copy
import traceback
from infant.config import config
from infant.agent.parser import parse
from infant.config import AgentParams
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.computer.computer import Computer
from infant.util.debug import print_messages
from infant.agent.state.state import State, AgentState
from infant.agent.memory.memory import ( 
    Task,
    Finish, 
    Critic,
    Memory, 
    Message, 
    Summarize, 
    TaskFinish, 
    IPythonRun,
    Userrequest,
    Classification, 
    LocalizationFinish,
)
from infant.util.logger import infant_logger as logger
from infant.util.special_case_handler import handle_reasoning_repetition, check_accumulated_cost
from infant.prompt.parse_user_input import parse_user_input_prompt
from infant.prompt.reasoning_prompt import reasoning_fake_user_response_prompt
from infant.prompt.tools_prompt import tool_stop, tool_fake_user_response_prompt
from infant.prompt.localization_prompt import (
    localization_fake_user_response_prompt,
    localization_check_dot_prompt,
    localization_check_rectangle_prompt,
)

from infant.prompt.reasoning_prompt import (
    reasoning_task_end_prompt
)

from infant.prompt.execution_prompt import (
    execution_task_end_prompt
)

from infant.agent.memory.retrieve_memory import (
    reasoning_memory_rtve, 
    classification_memory_rtve,
    critic_memory_rtve,
    localization_memory_rtve
)

from infant.agent.memory.restore_memory import (
    reasoning_memory_to_diag, 
    classification_memory_to_diag, 
    execution_memory_rtve,
    execution_memory_to_diag,
    critic_memory_to_diag,
    summary_memory_to_diag,
    truncate_output,
)

from infant.helper_functions.visual_helper_functions import localization_visual
from infant.helper_functions.browser_helper_function import localization_browser, convert_web_browse_commands, check_dropdown_options
from infant.agent.memory.file_related_memory import get_diff_patch, git_add_or_not

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, 
                 agent_config: AgentParams, 
                 api_llm: LLM_API_BASED | None = None, 
                 oss_llm: LLM_OSS_BASED | None = None, 
                 computer: Computer | None = None,
        ) -> None:
        """
        Initializes a new instance of the Agent.

        Parameters:
        - llm (LLM): The llm to be used by this agent
        """
        logger.info(f"Initializing Agent with parameters: agent_config: {agent_config}")
        if agent_config.use_oss_llm:
            self.llm = oss_llm
        else:
            self.llm = api_llm
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
        self.reasoning_task_end_prompt = reasoning_task_end_prompt
        self.execution_task_end_prompt = execution_task_end_prompt

    async def step(self):
        """
        Execute a single step (turn) of the agent's process asynchronously.
        """
        logger.info("Agent step started.")
        while True:
            try:
                if self.parse_request:
                    await self.usrreq_to_usrreqmty() 
                    
                # CoT reasoning until design a task
                await self.reasoning()
                
                # Determine the task category
                await self.classification()
                
                # Execute the task
                await self.execution()
                
                # critic the task
                if self.critic_execution:
                    await self.critic() 
                        
                # Summarize the task
                if self.summarize_execution: 
                    await self.summarize() 
                
                # upload to git
                git_add_or_not(user_response=True, computer=self.computer)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in agent step: {e}\n{traceback.format_exc()}")
                await self.change_agent_state(new_state=AgentState.ERROR)
            
    async def usrreq_to_usrreqmty(self,) -> Userrequest:
        if isinstance(self.state.memory_list[-1], Userrequest): # FIXME: implement a function to convert the user input to Userrequest class
            messages = await self.parse_user_request() 
            print(f'Messages in usrreq_to_usrreqmty: {messages}')
            resp, mem_blc= self.llm.completion(messages=messages, 
                                               stop=['</mandatory_standards>'])
            if mem_blc:
                self.state.memory_list.extend(mem_blc)
            mandatory_standards = parse(resp)
            if mandatory_standards != 'None':
                self.state.memory_list[-1].mandatory_standards = mandatory_standards
            logger.info(
                f"User Request: {self.state.memory_list[-1]}", 
                extra={
                    'msg_type': 'User_Request',}
            )
                
    async def reasoning(self,) -> Task:
        while not isinstance(self.state.memory_list[-1], (Task, Finish)):
            messages = await self.memory_to_input("reasoning", self.state.memory_list)
            # print_messages(messages, 'reasoning')
            # input("For debugging") # For setting up the first-time user
            resp, mem_blc= self.llm.completion(messages=messages, stop=['</analysis>', '</task>'])
            if mem_blc:
                self.state.memory_list.extend(mem_blc)
            memory = parse(resp) 
            if isinstance(memory, Message):
                self.state.memory_list.append(memory)
                reasoning_fake_user_response = Message(content=reasoning_fake_user_response_prompt)
                reasoning_fake_user_response.source = 'user'
                self.state.memory_list.append(reasoning_fake_user_response)
            else:
                self.state.memory_list.append(memory)
            await asyncio.sleep(0.3)
        if isinstance(self.state.memory_list[-1], Finish):
            await self.change_agent_state(new_state=AgentState.FINISHED)
            
    async def classification(self,) -> Classification:
        messages = await self.memory_to_input("classification", self.state.memory_list)
        # print(f'Messages in classification: {messages}')
        resp, mem_blc= self.llm.completion(messages=messages, stop=['</clf_task>'])
        if mem_blc:
            self.state.memory_list.extend(mem_blc)
        memory = parse(resp) 
        self.state.memory_list.append(memory)

    async def execution(self) -> TaskFinish:
        assert isinstance(self.state.memory_list[-1], Classification)
        cmd_set = self.state.memory_list[-1].cmd_set
        # print(f'cmd_set: {cmd_set}')
        interactive_elements = []
        # if the task is web_browse, we only need to execute the web_browse command
        if "web_browse" in cmd_set:
            cmd_set = {"web_browse"} # in-place change the cmd_set   
            dropdown_dict = None
            
        stop_signals = ['</task_finish>']
        for cmd in cmd_set:
            if cmd in tool_stop:
                stop_signals.append(tool_stop[cmd])
                
        while not isinstance(self.state.memory_list[-1], TaskFinish):
            messages = await self.memory_to_input("execution", self.state.memory_list, cmd_set = cmd_set)
            # print_messages(messages, 'execution')
            # input("For debugging") # For setting up the first-time user
            resp, mem_blc= self.llm.completion(messages=messages, stop=stop_signals)
            if mem_blc:
                self.state.memory_list.extend(mem_blc)

            memory = parse(resp) 
            if memory.runnable:
                # record the descritpion of the image
                if hasattr(memory, 'code') and memory.code:
                    tmp_code = memory.code
                    
                # localization, convert the image description to coordinate for accurate mouse click
                # For web_browse, we need to try localization_browser first & convert commands to correct format
                if cmd == 'web_browse':  
                    memory, finish_switch, interactive_elements = await localization_browser(self, memory, interactive_elements)
                    if not finish_switch:  
                        memory = await localization_visual(self, memory)
                    memory = convert_web_browse_commands(memory, finish_switch, dropdown_dict) # convert the commands to correct format
                else:
                    memory = await localization_visual(self, memory) # convert the image description to coordinate for accurate mouse click   
                                               
                method = getattr(self.computer, memory.action)
                result = await method(memory)
                
                # For web_browser, we need to check the dropdown menu
                chk_dropdown_result, dropdown_dict = await check_dropdown_options(self, cmd, interactive_elements)
                result += f'\n{chk_dropdown_result}'    
                    
                memory.result = truncate_output(output = result)
                
                # convert the coordinate back to image description
                if hasattr(memory, 'code') and memory.code:
                    memory.code = tmp_code
                    
                logger.info(memory, extra={'msg_type': 'Execution Result'})
                self.state.memory_list.append(memory)
            elif isinstance(memory, Message):
                self.state.memory_list.append(memory)
                execution_fake_user_response = Message(content=tool_fake_user_response_prompt)
                execution_fake_user_response.source = 'user'
                self.state.memory_list.append(execution_fake_user_response)
            else:
                self.state.memory_list.append(memory)
            await asyncio.sleep(0.3)
    
    async def critic(self,) -> bool:
        messages = await self.memory_to_input("critic", self.state.memory_list)
        # print_messages(messages, 'critic')
        resp, mem_blc= self.llm.completion(messages=messages)
        if mem_blc:
            self.state.memory_list.extend(mem_blc)
        critic_result = '<|exit_code=0|>' in resp
        if critic_result:
            memory= Critic(critic_result=critic_result)
        else:
            memory= Critic(critic_result=critic_result, reason=resp)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'Critic'})
        self.state.memory_list.append(memory)
        
        # If we delete the summarize, we should add the summary memory after the critic
        if not memory.critic_result:
            summary_memory = Summarize(summary = {})
            summary_memory.summary['reason'] = resp
            summary_memory.source = 'assistant'
            self.state.memory_list.append(summary_memory)
        
    async def summarize(self,) -> Summarize:
        # sum_attempts = 0
        assert isinstance(self.state.memory_list[-1], Critic)
        task_critic_result = self.state.memory_list[-1].critic_result
        reason = self.state.memory_list[-1].reason
        git_diff = get_diff_patch(self.computer)
        messages = await self.memory_to_input(
            "summary_true" if task_critic_result else "summary_false",
            self.state.memory_list,
            git_patch=git_diff,
        )
        # print_messages(messages, 'summarize')
        resp, mem_blc= self.llm.completion(messages=messages, stop=['</key_steps>'])
        if mem_blc:
            self.state.memory_list.extend(mem_blc)
        memory: Summarize = parse(resp)
        memory.summary['git_diff'] = git_diff
        if reason:
            memory.summary['reason'] = reason 
        logger.info(memory, extra={'msg_type': 'Summarize'})
        self.state.memory_list.append(memory)
        # if not isinstance(memory, Summarize):
        #     logger.warning("The summary is NOT a Summarize memory. Retry.")
        #     sum_attempts += 1
        #     if sum_attempts >= self.agent_config.max_sum_retries:
        #         logger.error("Summary Max retries reached. Developer should fix the prompt!")    
        #         await self.change_agent_state(new_state=AgentState.ERROR) 
    
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
            if self.state.agent_state in ('finished', 'error'):
                logger.info("Agent reached terminal state, stopping monitor.")
                break

    async def parse_user_request(self) -> dict:
        """
        Parse the user request into a structured input data format asynchronously.
        """
        memory_block = [self.state.memory_list[-1]]
        input_message = await self.memory_to_input("parse_user_request", memory_block)
        return input_message

    async def memory_to_input(self, case: str, memory_block: list | None = None, *args, **kwargs) -> list[dict]:
        """
        Asynchronously convert the agent's memory to a structured input data format.
        Based on different cases and memory block.

        Args:
        - case (str): The specific case to handle (e.g., reasoning, classification).
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

            #print(f"Flat block for processing: {flat_block}")
            if asyncio.iscoroutinefunction(processing_fn):
                results = await processing_fn(flat_block)
            else:
                results = processing_fn(flat_block) 
            return results

        if case == "parse_user_request":
            userrequest: Userrequest = memory_block[0]
            question = parse_user_input_prompt.format(user_request=userrequest.text)
            content = [
                    {
                        "type": "text",
                        "text": question
                    }
                ]
            if userrequest.images:
                for image in userrequest.images:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                        "url": image
                        }
                    })
            messages.append({"role": "user", "content": content})

        elif case == "reasoning":
            memory_block = await process_memory_block(memory_block, reasoning_memory_rtve)
            messages = reasoning_memory_to_diag(memory_block, end_prompt=self.reasoning_task_end_prompt)

        elif case == "classification":
            memory_block = await process_memory_block(memory_block, classification_memory_rtve)
            messages = classification_memory_to_diag(memory_block)

        elif case == "execution":
            cmd_set = kwargs.get('cmd_set', None)
            # print(f'cmd_set in memory_to_input: {cmd_set}')
            memory_block = await process_memory_block(memory_block, execution_memory_rtve)
            messages = execution_memory_to_diag(memory_block, cmd_set, end_prompt=self.execution_task_end_prompt)

        elif case == "critic":
            memory_block = await process_memory_block(memory_block, critic_memory_rtve)
            messages = critic_memory_to_diag(memory_block)

        elif case in ["summary_true", "summary_false"]:
            git_patch = kwargs.get('git_patch', None)
            memory_block = await process_memory_block(memory_block, critic_memory_rtve)
            messages = summary_memory_to_diag(memory_block, git_patch, case)
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
            # check if the reasoning output is repeated
            new_prompt = handle_reasoning_repetition(self.state.memory_list, 
                                                     max_repetition=self.agent_config.max_reasoning_iterations)
            if new_prompt:
                self.reasoning_task_end_prompt = new_prompt
            else:
                self.reasoning_task_end_prompt = reasoning_task_end_prompt
            
            # check if the accumulated cost exceeds the maximum allowed cost
            if check_accumulated_cost(self.llm.metrics.accumulated_cost, self.agent_config.max_budget_per_task):
                await self.change_agent_state(new_state=AgentState.ERROR)
            await asyncio.sleep(1)