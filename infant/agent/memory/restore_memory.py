import re
import copy
from infant.agent.memory.memory import (
    Memory,
    Analysis,
    Userrequest,
    Message,
    Summarize,
    Task,
    CmdRun,
    IPythonRun,
    BrowseURL,
    TaskFinish,
    Critic
)
from infant.config import config
from infant.agent.state.state import AgentState
from infant.agent.state.state import State
from infant.prompt.critic_prompt import critic_system_prompt, critic_task_prompt_wo_target, critic_task_prompt_w_target
from infant.prompt.reasoning_prompt import reasoning_sys_prompt, reasoning_provide_user_request, reasoning_task_end_prompt
from infant.prompt.task_prompt import (
    task_category,
    task_to_str_w_target, 
    task_to_str_wo_target,
    task_to_str_wo_summary_hands,
    task_to_str_wo_summary_wo_target_hands,
)

from infant.prompt.classification_prompt import (
    clf_task_to_str_w_target,
    clf_task_to_str_wo_target,
    clf_sys_prompt
)

from infant.prompt.summary_prompt import (
    smy_potential_issue_pt, 
    smy_new_code_pt,
    smy_git_diff_pt,
    smy_key_steps_pt,
    smy_reason_pt,
    summary_sys_prompt,
    summary_prompt_true,
    summary_prompt_false,
)

from infant.prompt.execution_prompt import (
    execution_split_userrequest_prompt,
    execution_critic_false_prompt,
    execution_critic_true_prompt,
    execution_task_end_prompt
)

from infant.prompt.localization_prompt import localization_prompt, localization_user_initial_prompt
from infant.prompt.tools_prompt import tool_document, tool_sys_msg, tool_example
from infant.agent.memory.retrieve_memory import (
    execution_memory_rtve, 
    retrieve_memory_further, 
    reasoning_memory_rtve_critic,
    critic_memory_rtve,
)

def merge_text_image_content(text, images):
    content = [
                        {
                            "type": "text",
                            "text": text
                        }
                    ]    
    if images:
        for image in images:
            content.append({
                    "type": "image_url",
                    "image_url": {
                    "url": image
                    }
                })   
    return content     
    
def base_memory_to_str(memory: Memory) -> str:
    '''
    convert the memory to a string.
    '''
    if isinstance(memory, CmdRun):
        text_content = f'{memory.thought}\n<execute_bash>\n{memory.command}\n</execute_bash>'
        content = merge_text_image_content(text_content, memory.images)
        return content
    elif isinstance(memory, Userrequest):
        text_content = reasoning_provide_user_request.format(user_request=memory.text, 
                                                     task_category=task_category)
        content = merge_text_image_content(text_content, memory.images)        
        return content
    elif isinstance(memory, IPythonRun):
        text_content = f'{memory.thought}\n<execute_ipython>\n{memory.code}\n</execute_ipython>'
        content = merge_text_image_content(text_content, memory.images)
        return content
    elif isinstance (memory, Analysis):
        text_content = f'<analysis>{memory.analysis}</analysis>'
        content = merge_text_image_content(text_content, None)
        return content
    elif isinstance(memory, TaskFinish):
        text_content = f'{memory.thought}'
        content = merge_text_image_content(text_content, None)
        return content
    elif isinstance(memory, Critic):
        if memory.reason is not None:
            return f'result: {memory.critic_result} reason: {memory.reason}'
        else:
            return f'result: {memory.critic_result}'
    elif isinstance(memory, Task):
        if memory.target is not None:
            if memory.summary != '':
                return task_to_str_w_target.format(summary=memory.summary, 
                                                   thought=memory.thought, 
                                                   task=memory.task, 
                                                   target=memory.target)
            else:
                return f'{memory.thought}<task>{memory.task}<target>{memory.target}</target></task>'
        else:
            if memory.summary != '':
                return task_to_str_wo_target.format(summary=memory.summary, 
                                    thought=memory.thought, 
                                    task=memory.task, )
            else:
                return f'{memory.thought}<task>{memory.task}</task>'
    elif isinstance(memory, Summarize):
        summary = ''
        tags = ['potential_issue', 'new_code', 'git_diff', 'key_steps', 'reason']
        for tag in tags:
            if tag in memory.summary:
                # if tag == 'potential_issue':
                #     summary += smy_potential_issue_pt.format(potential_issue=memory.summary[tag])
                # elif tag == 'new_code':
                #     summary += smy_new_code_pt.format(new_code=memory.summary[tag])
                # elif tag == 'git_diff':
                #     summary += smy_git_diff_pt.format(git_diff=memory.summary[tag])
                # elif tag == 'key_steps':
                #     summary += smy_key_steps_pt.format(key_steps=memory.summary[tag])
                # elif tag == 'reason':
                #     summary += smy_reason_pt.format(reason=memory.summary[tag])
                if tag == 'reason':
                    summary += smy_reason_pt.format(reason=memory.summary[tag])
        return summary
    elif isinstance(memory, Message):
        return memory.content
    elif isinstance(memory, BrowseURL):
        return f'<browse>{memory.url}</browse>'
    return ''

def truncate_output(output: str, max_chars: int = 10_000) -> str:
    """
    Truncate the middle of the output if it is too long.
    This will happen if some file content is too long.
    """
    if len(output) <= max_chars:
        return output
    half = max_chars // 2
    return (
        output[:half]
        + '\n[... Observation truncated due to length ...]\n'
        + output[-half:]
    )

def classification_memory_to_str(memory: Memory) -> str:
    if isinstance(memory, Task):
        if memory.target is not None:
            return clf_task_to_str_w_target.format(task=memory.task, target=memory.target)
        else:
            return clf_task_to_str_wo_target.format(task=memory.task)
    
def reasoning_memory_to_diag(memory_block: list[Memory], end_prompt: str) -> str:
    '''
    Use reasoning prompt to convert the memory_block to a string.
    '''
    messages = []
    messages.append({'role': 'user',
                     'content': reasoning_sys_prompt.format(task_category = task_category)})    
    for memory in memory_block:
        message = base_memory_to_str(memory)
        if message != '':
            messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                            'content': message})
        if hasattr(memory, 'result') and memory.result: 
            if 'Screenshot saved at' in memory.result: # image situation
                screenshot_path = memory.result.split('Screenshot saved at')[-2].strip()
                mount_path = config.workspace_mount_path
                # print(f"mount_path: {mount_path}")
                if screenshot_path.startswith("/workspace"):
                    image_path = screenshot_path.replace("/workspace", mount_path, 1)
                # print(f"image_path: {image_path}")
                image_path.replace("_label", '')
                image_url = image_base64_to_url(image_path)
                messages.append({'role': 'user',
                    'content': [{"type": "image_url","image_url": {"url": image_url}}]})
            else: # Text only situation
                messages.append({'role': 'user',
                    'content': memory.result}) 
    messages.append({'role': 'user',
                    'content': end_prompt})  
    return messages

def classification_memory_to_diag(memory_block: list[Memory]) -> str:
    '''
    Use reasoning prompt to convert the memory_block to a string.
    '''
    messages = []
    assert isinstance(memory_block[-1], Task)
    task = memory_block[-1]  
    messages.append({'role': 'user',
                     'content': clf_sys_prompt})    
    for memory in memory_block[:-1]:
        messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                        'content': base_memory_to_str(memory)})
    if task.target is not None:
        task_msg =  clf_task_to_str_w_target.format(task=task.task, target=task.target)
    else:
        task_msg = clf_task_to_str_wo_target.format(task=task.task)  
    messages.append({'role': 'user',
                    'content': task_msg})        
    return messages

def execution_memory_to_diag(memory_block: list[Memory], cmd_set, end_prompt):
    '''
    convert the exectuion memory_block to a string.
    '''
    messages = []
    tools_instructions = ''
    for cmd in cmd_set:
        if cmd in tool_document:
            tools_instructions = tools_instructions + tool_document[cmd] + '\n'
            example = tool_example[cmd] + '\n'
    messages.append({'role': 'user',
                     'content': tool_sys_msg.format(tools = tools_instructions, one_shot = example)})  
    # find the last Task in the memory block
    for i in range(len(memory_block) - 1, -1, -1):
        if isinstance(memory_block[i], Task):
            last_task: Task = memory_block[i]
            break
        
    for memory in memory_block:
        if isinstance(memory, Userrequest):
            content = merge_text_image_content(memory.text, memory.images)
            messages.append({'role': 'user','content': content})   
        elif isinstance(memory, Task):
            if memory.task == last_task.task: # If the task is the last task, emphasize it as the current task
                messages.append({'role': 'user',
                    'content': f'**Current Task**:\n{memory.task}'})                   
            else:
                if memory.target is not None:
                    messages.append({'role': 'user',
                        'content': f'Task:\n{memory.task}\nTarget:\n{memory.target}'})
                else:
                    messages.append({'role': 'user',
                        'content': f'{memory.task}'})     

        elif isinstance(memory, Critic):
            if memory.reason is not None:
                messages.append({'role': 'assistant',
                    'content': f'{execution_critic_false_prompt} reason: {memory.reason}'})
            else:
                messages.append({'role': 'assistant',
                    'content': execution_critic_true_prompt})                  
        else:
            message = base_memory_to_str(memory)
            if message != '':
                messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                                'content': message})
            
        if hasattr(memory, 'result') and memory.result: 
            if 'Screenshot saved at' in memory.result: # image situation
                screenshot_path = memory.result.split('Screenshot saved at')[-2].strip()
                mount_path = config.workspace_mount_path
                # print(f"mount_path: {mount_path}")
                if screenshot_path.startswith("/workspace"):
                    image_path = screenshot_path.replace("/workspace", mount_path, 1)
                # print(f"image_path: {image_path}")
                image_path.replace("_label", '')
                image_url = image_base64_to_url(image_path)
                messages.append({'role': 'user',
                    'content': [{"type": "image_url","image_url": {"url": image_url}}]})
            else: # Text only situation
                messages.append({'role': 'user',
                    'content': memory.result})      
    messages.append({'role': 'user',
                    'content': end_prompt})         
    return messages

def localization_memory_to_diag(memory_block: list[Memory]):
    '''
    convert the exectuion memory_block to a string.
    '''
    # print('Debugging localization_memory_to_diag')
    messages = []
    pattern = r"mouse_(left_click|double_click|move|right_click)\((['\"])(.*?)\2, (['\"])(.*?)\4\)"
    match = re.search(pattern, memory_block[0].code)
    if match:
        item_to_click = match.group(3) 
        position_description = match.group(5) 
    messages.append({'role': 'user',
    'content': localization_prompt.format(item_to_click = item_to_click)})   
    messages.append({'role': 'user',
    'content': localization_user_initial_prompt.format(item_to_click = item_to_click, Location = position_description)})   
    for index, memory in enumerate(memory_block):
        if hasattr(memory, 'result') and memory.result is not None and 'Screenshot saved at' in memory.result: # image situation
            screenshot_path = memory.result.split('Screenshot saved at')[-1].strip()
            mount_path = config.workspace_mount_path
            # print(f"mount_path: {mount_path}")
            if screenshot_path.startswith("/workspace"):
                image_path = screenshot_path.replace("/workspace", mount_path, 1)
            # print(f"image_path: {image_path}")
            image_url = image_base64_to_url(image_path)
            if index == 0:
                messages.append({'role': 'user',
                    'content': [{"type": "image_url","image_url": {"url": image_url}}]})
            else:
                messages.append({'role': 'assistant',
                    'content': base_memory_to_str(memory)})
                messages.append({'role': 'user',
                    'content': [{"type": "image_url","image_url": {"url": image_url}}]})
        else: # Text only situation
            messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                'content': base_memory_to_str(memory)})          
    return messages

def critic_memory_to_diag(memory_block: list[Memory]):
    '''
    convert the critic memory_block to a string.
    '''
    messages = []
    messages.append({'role': 'user',
                     'content': critic_system_prompt}) 
    for memory in memory_block:
        if isinstance(memory, Userrequest):
            messages.append({'role': 'user','content': memory.content})   
        elif isinstance(memory, Task):
            if memory.target is not None:
                messages.append({'role': 'user',
                    'content': f'Task:\n{memory.task}\nTarget:\n{memory.target}'})
            else:
                messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                    'content': f'Task:\n{memory.task}'})                     
        else:
            messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                'content': base_memory_to_str(memory)})
        if hasattr(memory, 'result') and memory.result: 
            if 'Screenshot saved at' in memory.result: # image situation
                screenshot_path = memory.result.split('Screenshot saved at')[-2].strip()
                mount_path = config.workspace_mount_path
                # print(f"mount_path: {mount_path}")
                if screenshot_path.startswith("/workspace"):
                    image_path = screenshot_path.replace("/workspace", mount_path, 1)
                # print(f"image_path: {image_path}")
                image_path.replace("_label", '')
                image_url = image_base64_to_url(image_path)
                messages.append({'role': 'user',
                    'content': [{"type": "image_url","image_url": {"url": image_url}}]})
            else: # Text only situation
                messages.append({'role': 'user',
                    'content': memory.result})    
                
    # Find the last Task in the memory block
    for i in range(len(memory_block) - 1, -1, -1):
        if isinstance(memory_block[i], Task):
            last_task: Task = memory_block[i]
            break

    if last_task.target is not None:
        critic_msg = critic_task_prompt_w_target.format(task = last_task.task,target=last_task.target)
    else:
        critic_msg = critic_task_prompt_wo_target.format(task = last_task.task)
    messages.append({'role': 'user',
                    'content': critic_msg})
    return messages

def summary_memory_to_diag(memory_block: list[Memory], git_patch, case):
    '''
    convert the summary memory_block to a string.
    '''
    messages = []
    messages.append({'role': 'user',
                     'content': summary_sys_prompt}) 
    for memory in memory_block:
        if isinstance(memory, Userrequest):
            messages.append({'role': 'user','content': memory.content})   
        elif isinstance(memory, Task):
            if memory.target is not None:
                messages.append({'role': 'user',
                    'content': f'Task:\n{memory.task}\nTarget:\n{memory.target}'})
            else:
                messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                    'content': f'Task:\n{memory.task}'})                     
        else:
            messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                'content': base_memory_to_str(memory)})
        if hasattr(memory, 'result') and memory.result: 
            if 'Screenshot saved at' in memory.result: # image situation
                screenshot_path = memory.result.split('Screenshot saved at')[-2].strip()
                mount_path = config.workspace_mount_path
                # print(f"mount_path: {mount_path}")
                if screenshot_path.startswith("/workspace"):
                    image_path = screenshot_path.replace("/workspace", mount_path, 1)
                # print(f"image_path: {image_path}")
                image_path.replace("_label", '')
                image_url = image_base64_to_url(image_path)
                messages.append({'role': 'user',
                    'content': [{"type": "image_url","image_url": {"url": image_url}}]})
            else: # Text only situation
                messages.append({'role': 'user',
                    'content': memory.result})  
    if git_patch:
        messages.append({"role": "user", "content": git_patch})
    if case == "summary_true":
        messages.append({"role": "user", "content": summary_prompt_true})
    else:
        messages.append({"role": "user", "content": summary_prompt_false})    
    return messages

def hands_memory_to_str(memory: Memory) -> str:
    '''
    convert the action to a string.
    '''
    if isinstance(memory, CmdRun):
        return f'{memory.thought}\n<execute_bash>\n{memory.command}\n</execute_bash>'
    elif isinstance(memory, IPythonRun):
        return f'{memory.thought}\n<execute_ipython>\n{memory.code}\n</execute_ipython>'
    elif isinstance (memory, Analysis):
        return f'<analysis>{memory.analysis}</analysis>'
    elif isinstance(memory, Task):
        if memory.target is not None:
            if memory.summary != '':
                return task_to_str_w_target.format(summary=memory.summary, 
                                                   thought=memory.thought, 
                                                   task=memory.task, 
                                                   target=memory.target)
            else:
                return task_to_str_wo_summary_hands.format(thought=memory.thought, 
                                    task=memory.task, 
                                    target=memory.target)
        else:
            if memory.summary != '':
                return task_to_str_wo_target.format(summary=memory.summary, 
                                    thought=memory.thought, 
                                    task=memory.task, )
            else:
                return task_to_str_wo_summary_wo_target_hands.format(thought=memory.thought, 
                                    task=memory.task)
    elif isinstance(memory, Summarize):
        summary = ''
        tags = ['potential_issue', 'new_code', 'git_diff', 'key_steps', 'reason']
        for tag in tags:
            if tag in memory.summary:
                if tag == 'potential_issue':
                    summary += smy_potential_issue_pt.format(potential_issue=memory.summary[tag])
                elif tag == 'new_code':
                    summary += smy_new_code_pt.format(new_code=memory.summary[tag])
                elif tag == 'git_diff':
                    summary += smy_git_diff_pt.format(git_diff=memory.summary[tag])
                elif tag == 'key_steps':
                    summary += smy_key_steps_pt.format(key_steps=memory.summary[tag])
                elif tag == 'reason':
                    summary += smy_reason_pt.format(reason=memory.summary[tag])
        return summary
    elif isinstance(memory, Message):
        return memory.content
    elif isinstance(memory, BrowseURL):
        return f'<browse>{memory.url}</browse>'
    return ''

def image_base64_to_url(image_path: str) -> str:
    '''
    convert the image to a base64 string.
    '''
    import base64
    import os
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File not found: {image_path}")
    with open(image_path, "rb") as img_file:
        base64_data = base64.b64encode(img_file.read()).decode("utf-8")
    image_url = f"data:image/png;base64,{base64_data}"
    return image_url



def brain_get_memory_message(memory: Memory) -> dict[str, str] | None:
    '''
    convert the action to a message that can be displayed to the llm.
    '''
    if (
        isinstance(memory, CmdRun)
        or isinstance(memory, IPythonRun)
        or isinstance(memory, Message)
        or isinstance(memory, Task)
        or isinstance(memory, Analysis)
        or isinstance(memory, BrowseURL)
    ):
        return {
            'role': 'user' if memory.source == 'user' else 'assistant',
            'content': brain_memory_to_str(memory),
        }
    elif isinstance(memory, Summarize):
        return {'role': 'user', 'content': brain_memory_to_str(memory)}
    return None


def hands_get_memory_message(memory: Memory) -> dict[str, str] | None:
    '''
    convert the action to a message that can be displayed to the llm.
    '''
    if (
        isinstance(memory, CmdRun)
        or isinstance(memory, IPythonRun)
        or isinstance(memory, Message)
        or isinstance(memory, Task)
        or isinstance(memory, Analysis)
        or isinstance(memory, BrowseURL)
    ):
        return {
            'role': 'user' if memory.source == 'user' else 'assistant',
            'content': hands_action_to_str(memory),
        }
    elif isinstance(memory, Summarize):
        return {'role': 'user', 'content': hands_action_to_str(memory)}
    return None


def get_observation_message(obs) -> dict[str, str] | None:
    '''
    get the observation message for the agent. General **CoT** version.
    convert the observation to a message that can be displayed to the llm.
    '''
    if isinstance(obs, CmdOutputObservation):
        content = 'OBSERVATION:\n' + truncate_observation(obs.content)
        content += (
            f'\n[Command {obs.command_id} finished with exit code {obs.exit_code}]'
        )
        return {'role': 'user', 'content': content}
    elif isinstance(obs, IPythonRunCellObservation):
        content = 'OBSERVATION:\n' + obs.content
        # replace base64 images with a placeholder
        splitted = content.split('\n')
        for i, line in enumerate(splitted):
            if '![image](data:image/png;base64,' in line:
                splitted[i] = (
                    '![image](data:image/png;base64, ...) already displayed to user'
                )
        content = '\n'.join(splitted)
        content = truncate_observation(content)
        return {'role': 'user', 'content': content}
    elif isinstance(obs, AgentTaskSummarizeObservation):
        content = obs.content
        return {'role': 'user', 'content': content}
    elif isinstance(obs, BrowserOutputObservation):
        
        content = (
            f'**BrowserOutputObservation**\n'
            f'URL: {obs.url}\n'
            f'Status code: {obs.status_code}\n'
            f'Error: {obs.error}\n'
            f'Open pages: {obs.open_pages_urls}\n'
            f'Active page index: {obs.active_page_index}\n'
            f'Last browser action: {obs.last_browser_action}\n'
            f'Last browser action error: {obs.last_browser_action_error}\n'
            f'Focused element bid: {obs.focused_element_bid}\n'
            f'CONTENT: {obs.content}\n'
        )
        return {'role': 'user', 'content': content}


def restore_brain_memory(state: State, messages: list[dict[str, str]] = []) -> list | None:
    '''
    convert the state.history to a message that can be displayed to the llm.
    '''
    if state.agent_state == AgentState.FINISHED:
        summarize_all_steps = True
    else:
        summarize_all_steps = False
    if state.evaluation:
        memory = critic_memory_rtve(state.memory_list, summarize_all_steps)
    elif state.critic:
        memory = reasoning_memory_rtve_critic(state.memory_list, summarize_all_steps)
        memory[0][0].content = 'I am trying to solve the following problem:\n'+ state.user_question + 'I made the following analysis\n:'
        memory.append((Message(content = critic_prompt), NullObservation('')))
    else:
        memory = retrieve_brain_memory(state.memory_list, summarize_all_steps)
    messages = brain_memory_to_message(memory,messages)
    return messages


def restore_hands_memory(state: State, messages: list[dict[str, str]] = [], max_chars = 10000) -> list | None:
    '''
    convert the state.history to a message that can be displayed to the llm.
    '''
    if state.agent_state == AgentState.FINISHED:
        summarize_all_steps = True
    else:
        summarize_all_steps = False
    memory = execution_memory_rtve(state.history, summarize_all_steps)
    messages = hands_memory_to_message(memory,messages)
    good_news = check_dialogue_length(messages, max_chars=max_chars)
    while not good_news:
        backup_messages = copy.deepcopy(messages)
        memory = retrieve_memory_further(memory,good_news=False)
        messages = hands_memory_to_message(memory, messages = [])
        dialogue_length_condition = check_dialogue_length(messages, max_chars=max_chars)
        messages_identical_condition = messages == backup_messages
        if dialogue_length_condition or messages_identical_condition:
            good_news = True
    return messages
    
    
def brain_memory_to_message(memory: list, messages: list[dict[str, str]] = []) -> list[dict[str, str]]:
    for prev_action, obs in memory:
        action_message = brain_get_memory_message(prev_action)
        if action_message:
            messages.append(action_message)

        obs_message = get_observation_message(obs)
        if obs_message:
            messages.append(obs_message)
    return messages


def hands_memory_to_message(memory: list, messages: list[dict[str, str]] = []) -> list[dict[str, str]]:
    for prev_action, obs in memory:
        action_message = hands_get_memory_message(prev_action)
        if action_message:
            messages.append(action_message)

        obs_message = get_observation_message(obs)
        if obs_message:
            messages.append(obs_message)
    return messages


def check_dialogue_length(messages: list[dict[str, str]], max_chars: int = 10_000) -> bool:
    '''
    check the length of the dialogue.
    '''
    total_length = 0
    for message in messages:
        total_length += len(message['content'])
    return total_length < max_chars