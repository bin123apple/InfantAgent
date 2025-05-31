import os
import base64
import mimetypes
from PIL import Image
from infant.agent.memory.memory import (
    Memory,
    Analysis,
    Userrequest,
    Message,
    Task,
    CmdRun,
    IPythonRun,
    TaskFinish,
    Finish
)
from infant.util.logger import infant_logger as logger
from infant.prompt.planning_prompt import planning_sys_prompt, planning_provide_user_request
from infant.prompt.task_prompt import task_category
from infant.prompt.classification_prompt import (
    clf_task_to_str_w_target,
    clf_task_to_str_wo_target,
    clf_sys_prompt
)
from infant.prompt.tools_prompt import tool_document, tool_sys_msg, tool_example, tool_advanced


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
        text_content = planning_provide_user_request.format(user_request=memory.text)
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
    elif isinstance(memory, Task):
        return f'{memory.thought}<task>{memory.task}</task>'
    elif isinstance(memory, Message):
        return memory.thought
    elif isinstance(memory, Finish):
        return f'<finish>{memory.thought}</finish>'
    return ''

def truncate_output(output: str, max_chars: int = 6_000) -> str:
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

def compress_image(image_path: str) -> str:
    """
    If the image is larger than 5MB, convert it to JPEG format.
    """
    max_bytes = 5 * 1024 * 1024  # 5MB
    try:
        # check file size and extension
        size = os.path.getsize(image_path)
        ext = os.path.splitext(image_path)[1].lower()

        # if the image is larger than 5MB and is a PNG, convert it to JPEG
        if ext == '.png' and size > max_bytes:
            jpeg_path = os.path.splitext(image_path)[0] + '.jpg'
            if os.path.exists(jpeg_path):
                return jpeg_path
            logger.info(f"The size of current image is {size}, converting {image_path} (>5MB) to JPEG…")

            img = Image.open(image_path).convert('RGB')
            img.save(jpeg_path, 'JPEG')
            return jpeg_path

        return image_path

    except Exception as e:
        logger.error(f"Fail to compress/convert image: {e}")
        return image_path
  
def merge_mutimodal_content(memory: Memory, messages: list, mount_path: str):
    content = []
    text = memory.result
    content.append({"type": "text","text": text})
    if '<Screenshot saved at>' in memory.result: # image situation
        lines = memory.result.splitlines()
        # find the last line containing '<Screenshot saved at>'
        last_line = None
        for line in reversed(lines):
            if '<Screenshot saved at>' in line:
                last_line = line
                break
        # extract the path
        if last_line is not None:
            screenshot_path = last_line.split('<Screenshot saved at>')[-1].strip()
        if screenshot_path.startswith("/workspace"):
            image_path = screenshot_path.replace("/workspace", mount_path, 1)
            image_path = compress_image(image_path)
        image_url = image_base64_to_url(image_path)
        content.append({"type": "image_url","image_url": {"url": image_url}})
    messages.append({'role': 'user','content': content}) 
    return messages    
    
def planning_memory_to_diag(memory_block: list[Memory], end_prompt: str, mount_path: str) -> str:
    '''
    Use planning prompt to convert the memory_block to a string.
    '''
    messages = []
    messages.append({'role': 'user',
                     'content': planning_sys_prompt.format(task_category = task_category)})    
    for memory in memory_block:
        message = base_memory_to_str(memory)
        if message != '':
            messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                            'content': message})
        if hasattr(memory, 'result') and memory.result: 
            messages = merge_mutimodal_content(memory, messages, mount_path)
    messages.append({'role': 'user',
                    'content': end_prompt})  
    return messages

def classification_memory_to_diag(memory_block: list[Memory]) -> str:
    '''
    Use planning prompt to convert the memory_block to a string.
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

def execution_memory_to_diag(memory_block: list[Memory], cmd_set, end_prompt, mount_path: str) -> str:
    '''
    convert the execution memory_block to a string.
    '''
    messages = []
    tools_instructions = ''
    for cmd in cmd_set:
        if cmd in tool_document:
            tools_instructions = tools_instructions + tool_document[cmd] + tool_advanced
            # example = tool_example[cmd] + tool_advanced_one_shot
            example = tool_example[cmd] # FIXME: Rearrange the tool_advanced_one_shot
            # note = tool_note[cmd] + '\n'
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
                
        else:
            message = base_memory_to_str(memory)
            if message != '':
                messages.append({'role': 'user' if memory.source == 'user' else 'assistant',
                                'content': message})
            
        if hasattr(memory, 'result') and memory.result: 
            messages = merge_mutimodal_content(memory, messages, mount_path)
    messages.append({'role': 'user',
                    'content': end_prompt.format(task = last_task.task)})         
    return messages

def image_base64_to_url(image_path: str) -> str:
    """
    Convert an image file to a base64 data URL, auto-detecting the MIME type.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File not found: {image_path}")
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/png"

    with open(image_path, "rb") as img_file:
        b64 = base64.b64encode(img_file.read()).decode("utf-8")

    return f"data:{mime_type};base64,{b64}"

def check_dialogue_length(messages: list[dict[str, str]], max_chars: int = 10_000) -> bool:
    '''
    check the length of the dialogue.
    '''
    total_length = 0
    for message in messages:
        total_length += len(message['content'])
    return total_length < max_chars