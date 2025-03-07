import re
import copy
import time
import traceback
from infant.config import config
from infant.agent.parser import parse
from infant.config import AgentParams
from infant.llm.llm_api_base import LLM_API_BASED
from infant.llm.llm_oss_base import LLM_OSS_BASED
from infant.sandbox.sandbox import Sandbox
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
    localization_memory_to_diag,
    truncate_output,
    image_base64_to_url
)

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
                 sandbox: Sandbox | None = None,
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
        self.sandbox = sandbox
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
                git_add_or_not(user_response=True, sandbox=self.sandbox)
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
                    
                await self.localizaiton(memory)                                  
                method = getattr(self.sandbox, memory.action)
                # print('Debugging method in execution')
                result = await method(memory)
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
        # input("For debugging") # For setting up the first-time user
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
        git_diff = get_diff_patch(self.sandbox)
        messages = await self.memory_to_input(
            "summary_true" if task_critic_result else "summary_false",
            self.state.memory_list,
            git_patch=git_diff,
        )
        # print_messages(messages, 'summarize')
        # input("For debugging") # For setting up the first-time user
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

    async def localizaiton(self, memory):
        '''
        Convert the image description to coordinate for accurate mouse click
        '''
        if isinstance(memory, IPythonRun):
            pattern = r"mouse_(left_click|double_click|move|right_click)\((['\"])(.*?)\2, (['\"])(.*?)\4\)"
            # print(f'Debugging memory.code in execution: {memory.code}')
            match = re.search(pattern, memory.code)
            # print(f'Debugging match in execution: {match}')
            if match:
                # Take a screenshot
                action = match.group(1)
                scr_memory = IPythonRun(code=f'take_screenshot()')
                method = getattr(self.sandbox, scr_memory.action)
                result = await method(scr_memory)
                memory.result = result
                logger.info(memory, extra={'msg_type': 'Execution Result'})
                
                # Find the coordination
                coordination =  await self.image_description_to_coordinate(memory)
                if coordination == '':
                    logger.info("Coordination is an empty string.")
                    memory.code = f"mouse_{action}(-1, -1)"
                elif coordination == 'exit':
                    logger.info("Coordination is 'exit'. Exiting the function.")
                    memory.code = f"mouse_{action}(-1, -1)"
                else:
                    try:
                        coord_tuple = eval(coordination)  
                        if isinstance(coord_tuple, tuple) and len(coord_tuple) == 2:
                            x, y = coord_tuple  
                            memory.code = f"mouse_{action}({x}, {y})" # replace the image description with the coordinate
                            logger.info(f"Mouse clicked at coordinates: ({x}, {y})")
                        else:
                            logger.error("Coordination is not a valid tuple.")
                    except (SyntaxError, ValueError) as e:
                        logger.error(f"Failed to parse coordination: {coordination}. Error: {e}")          

    async def image_description_to_coordinate(self, mouse_click_action: Memory):
        """
        Convert the image description to coordinate for accurate mouse click.
        """
        # Initialize the localization memory block
        localization_memory_block = []
        localization_memory_block.append(mouse_click_action) 
        stop_signals = ['</loca_finish>', '</execute_ipython>']
            
        while not isinstance(localization_memory_block[-1], LocalizationFinish):
            # rtve_localization_memory_block = localization_memory_rtve(localization_memory_block)
            messages = localization_memory_to_diag(localization_memory_block)
            # printable_messages = [
            #     {
            #         "role": message["role"],
            #         "content": message["content"] if isinstance(message.get("content"), str) else "content is a image"
            #     }
            #     for message in messages
            # ]
            # print(f'Messages in image_description_to_coordinate: {printable_messages}')
            resp, mem_blc= self.llm.completion(messages=messages, stop=stop_signals)
            if mem_blc:
                localization_memory_block.extend(mem_blc)
            # Use different model to get the analysis the image
            # resp, mem_blc= self.llm.completion(messages=messages, 
            #                              stop=stop_signals,
            #                              model='',
            #                              api_key='')
            # if mem_blc:
            #     self.state.memory_list.extend(mem_blc)
            memory = parse(resp)
            # check if the zoom in/localization command is correct
            memory = await self.localizaiton_correction(memory, 
                                                   localization_memory_block,)
            
            if memory.runnable:
                method = getattr(self.sandbox, memory.action)
                result = await method(memory)
                memory.result = result
                logger.info(memory, extra={'msg_type': 'Execution Result'})
                localization_memory_block.append(memory)
            elif isinstance(memory, Message):
                localization_memory_block.append(memory)
                execution_fake_user_response = Message(content=localization_fake_user_response_prompt)
                execution_fake_user_response.source = 'user'
                localization_memory_block.append(execution_fake_user_response)
            else:
                localization_memory_block.append(memory)
        if isinstance(localization_memory_block[-1], LocalizationFinish):
            coordination = localization_memory_block[-1].coordination
        self.state.memory_list.extend(localization_memory_block[1:])
        return coordination

    async def localizaiton_correction(self, localization_action: Memory, 
                                localization_memory_block: list[Memory],):
        '''
        Check if the zoom in/localization command is correct
        '''
        # Initialize the localization_check memory block
        rtve_localization_memory_block = localization_memory_rtve(localization_memory_block)
        localization_correction_memory_block = copy.deepcopy(rtve_localization_memory_block)
        print(f'localization_correction_memory_block: {localization_correction_memory_block}')
        last_py_memory = next(
            (memory for memory in reversed(localization_correction_memory_block) if memory.__class__.__name__ == "IPythonRun"),
            IPythonRun(code = 'localization(top_left=0,0),length=1920')  # If there is not found, use a default value
        )
        stop_signals = ['</loca_finish>', '</execute_ipython>']
        
        if 'localization(' in last_py_memory.code:
            regex = r"top_left\s*=\s*\((\d+,\s*\d+)\)|length\s*=\s*(\d+)"
            matches = re.findall(regex, last_py_memory.code)
            for match in matches:
                if match[0]:  # Matches top_left
                    last_top_left = tuple(map(int, match[0].split(',')))
                if match[1]:  # Matches length
                    last_length = int(match[1])
        else:
            # Use full screen as the default value
            last_top_left = (0, 0)
            last_length = 1920
            
        # convert previous memory block to block
        messages = localization_memory_to_diag(localization_correction_memory_block)

        while not isinstance(localization_action, Message):
            if isinstance(localization_action, LocalizationFinish):
                messages.append({'role': 'assistant', 'content': f'{localization_action.thought}\n<loca_finish>{localization_action.coordination}</loca_finish>'})
            elif isinstance(localization_action, IPythonRun) and 'localization' in localization_action.code:
                messages.append({'role': 'assistant', 'content': f'{localization_action.thought}\n<execute_ipython>{localization_action.code}</execute_ipython>'})
            else:
                return localization_action
            
            # draw a red rectangle or a dot on the image for the localization correction
            if isinstance(localization_action, LocalizationFinish):
                coordination = localization_action.coordination
                # draw a red dot if this is the last step
                draw_dot = IPythonRun(code=f'draw_dot({last_top_left}, {last_length}, {coordination})')
                print(f'draw_dot: {draw_dot}')
                method = getattr(self.sandbox, draw_dot.action)
                result = await method(draw_dot)
                print(f'draw_dot result: {result}')
                if 'Screenshot saved at' in result:
                    screenshot_path = result.split('Screenshot saved at')[-1].strip()
                    mount_path = config.workspace_mount_path
                    if screenshot_path.startswith("/workspace"):
                        image_path = screenshot_path.replace("/workspace", mount_path, 1)
                    image_url = image_base64_to_url(image_path)
                    messages.append({'role': 'user',
                        'content': [{'type': 'text', 'text': localization_check_dot_prompt},
                            {"type": "image_url","image_url": {"url": image_url}}]})
                    
                    # print the messages for debugging
                    # printable_messages = [
                    #     {
                    #         "role": message["role"],
                    #         "content": message["content"] if isinstance(message.get("content"), str) else "content is a image"
                    #     }
                    #     for message in messages
                    # ]
                    # print(f'Messages in localizaiton_check: {printable_messages}')
                    dc_messages = copy.deepcopy(messages)
                    resp, _ = self.llm.completion(messages=dc_messages, stop=stop_signals)
                    if '<|command_correct|>' in resp:
                        return localization_action
                    else:
                        localization_action = parse(resp)
                else:
                    return localization_action
            elif isinstance(localization_action, IPythonRun):
                if 'localization' in localization_action.code:
                    # draw a red rectangle if this is the intermediate step
                    regex = r"top_left\s*=\s*\((\d+,\s*\d+)\)|length\s*=\s*(\d+)"
                    matches = re.findall(regex, localization_action.code)
                    for match in matches:
                        if match[0]:  # Matches top_left
                            top_left = tuple(map(int, match[0].split(',')))
                        if match[1]:  # Matches length
                            length = int(match[1])
                    draw_rectangle = IPythonRun(code=f'draw_rectangle({last_top_left}, {last_length}, {top_left}, {length})')
                    print(f'draw_rectangle: {draw_rectangle}')
                    method = getattr(self.sandbox, draw_rectangle.action)
                    result = await method(draw_rectangle)
                    print(f'draw_rectangle result: {result}')
                    if 'Screenshot saved at' in result:
                        screenshot_path = result.split('Screenshot saved at')[-1].strip()
                        mount_path = config.workspace_mount_path
                        if screenshot_path.startswith("/workspace"):
                            image_path = screenshot_path.replace("/workspace", mount_path, 1)
                        image_url = image_base64_to_url(image_path)
                        messages.append({'role': 'user',
                            'content': [{'type': 'text', 'text': localization_check_rectangle_prompt},
                                {"type": "image_url","image_url": {"url": image_url}}]})
                        
                        # print the messages for debugging
                        # printable_messages = [
                        #     {
                        #         "role": message["role"],
                        #         "content": message["content"] if isinstance(message.get("content"), str) else "content is a image"
                        #     }
                        #     for message in messages
                        # ]
                        # print(f'Messages in localizaiton_check: {printable_messages}')
                        dc_messages = copy.deepcopy(messages)
                        resp,_ = self.llm.completion(messages=dc_messages, stop=stop_signals)
                        if '<|command_correct|>' in resp:
                            return localization_action
                        else:
                            localization_action = parse(resp)
                    else:
                        return localization_action
                else:
                    return localization_action
            else:
                return localization_action
        return localization_action
            
            

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