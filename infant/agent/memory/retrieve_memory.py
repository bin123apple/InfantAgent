import re
import copy
import subprocess
from infant.agent.memory.memory import (
    Classification,
    Summarize,
    Critic,
    Message,
    Task,
    TaskFinish,
    LocalizationFinish,
    IPythonRun,
)


from infant.util.logger import infant_logger as logger

def reasoning_memory_rtve_critic(memory_list: list, summarize_all_steps=False) -> list | None:
    """
    Retrieve the memory from the state.history for reaosning with critic.
    
    Input: memory_list: All the memory.
    output: retrieved memory block.
    
    For intermediate steps, the memory should only contain:
    - Remove all the content between Task and Summarize pairs.
    - Keep all other content.
    - For the final step (Agent finished all the tasks), the memory should contain all the detailed memory.
    - If "potential_issue" is found in the summary, discard the Summarize.
    """
    dc_ml = copy.deepcopy(memory_list)
    memory_block = []
    if summarize_all_steps:
        memory_block = dc_ml
    else:
        skip = False
        for i in range(len(dc_ml)):
            memory = dc_ml[i]
            if isinstance(memory, Task):
                # When encountering an Task, start skipping until an Summarize is found
                skip = True
                memory_block.append(memory)  # Keep the Task
            elif isinstance(memory, Summarize):
                # Stop skipping when encountering an Summarize
                skip = False
                if 'potential_issue' not in memory.summary:
                    memory_block.append(memory)  # Keep the AgentSummarizeAction
            elif not skip:
                # Keep everything outside the skip range
                memory_block.append(memory)
    return memory_block


# def reasoning_memory_rtve(memory_list: list, summarize_all_steps=False) -> list | None:
#     """
#     Retrieve the memory from the state.history for reaosning.
    
#     Input: memory_list: All the memory.
#     output: retrieved memory block.
    
#     For intermediate steps, the memory should only contain:
#     - Remove all the content between Task and Summarize pairs.
#     - Keep all other content.
#     - For the final step (Agent finished all the tasks), the memory should contain all the detailed memory.
#     """
#     if not isinstance(memory_list, list):
#         memory_list = [memory_list]
        
#     dc_ml = copy.deepcopy(memory_list)
#     memory_block = []
#     if summarize_all_steps:
#         memory_block = dc_ml
#     else:
#         skip = False
#         for i in range(len(dc_ml)):
#             memory = dc_ml[i]
#             if isinstance(memory, Task):
#                 # When encountering an Task, start skipping until an Summarize is found
#                 skip = True
#                 memory_block.append(memory)  # Keep the Task
#             elif isinstance(memory, Summarize):
#                 # Stop skipping when encountering an Summarize
#                 skip = False
#                 memory_block.append(memory)  # Keep the Summarize
#             elif not skip:
#                 # Keep everything outside the skip range
#                 memory_block.append(memory)
    
#     return memory_block

def reasoning_memory_rtve(memory_list: list, summarize_all_steps=False) -> list | None:
    """
    Retrieve the memory from the state.history for reaosning.
    
    Input: memory_list: All the memory.
    output: retrieved memory block.
    
    For intermediate steps, the memory should only contain:
    - Only delete the Critic and Classification memory.
    """
    if not isinstance(memory_list, list):
        memory_list = [memory_list]
        
    dc_ml = copy.deepcopy(memory_list)
    memory_block = []
    if summarize_all_steps:
        memory_block = dc_ml
    else:
        for i in range(len(dc_ml)):
            memory = dc_ml[i]
            if not isinstance(memory, (Classification)):  
                memory_block.append(memory)
    
    return memory_block


def critic_memory_rtve(memory_list: list, summarize_all_steps=False) -> list | None:
    """
    Retrieve the memory from the state.history for execution without user request.
    
    Input: memory_list: All the memory.
    output: retrieved memory block.
    
    For intermediate steps, the memory should only contain:
    - Remove all the content before the last Task.
    - Keep all other content.
    - For the final step (Agent finished all the tasks), the memory should contain all the detailed memory, execpt Classification & Critic.
    """
    dc_ml = copy.deepcopy(memory_list)
    memory_block = []
    if summarize_all_steps:
        memory_block = dc_ml
    else:
        last_task_index = None
        for i in reversed(range(len(dc_ml))):
            memory = dc_ml[i]
            if isinstance(memory, Task):
                last_task_index = i
                break
        
        for i in range(1, last_task_index):
            memory = dc_ml[i]
            if isinstance(memory, Task):
                memory_block.append(memory)
        for memory in dc_ml[last_task_index:]:
            if not isinstance(memory, (Critic,
                                        Message,
                                        Classification, 
                                        LocalizationFinish)):  
                if isinstance(memory, IPythonRun):
                    if 'localization(' not in memory.code:
                        memory_block.append(memory)
                else:
                    memory_block.append(memory)
    return memory_block

# def execution_memory_rtve(memory_list: list, summarize_all_steps=False) -> list | None:
#     '''
#     Retrieve the memory from the state.history for execution without user request.
    
#     Input: memory_list: All the memory.
#     output: retrieved memory block.
    
#     For intermediate steps, the memory should only contain:
#     - Keep the first memory. # FIXME: I assume the first memory is userrequest, for multi-turns, we need to update this.
#     - Keep the last Task and all memory after it except the classification memory.
#     - For prior memory before the last Task, only keep those where memory is Task.
#     - For the final step (Agent finished all the tasks), the memory should contain all the detailed memory execpt Classification & Critic.
#     '''
#     memory_block = []
#     dc_ml = copy.deepcopy(memory_list)

#     # If all the tasks are finished and the agent is asked to summarize all the steps
#     if summarize_all_steps:
#         memory_block = dc_ml
#     else:
#         # Find the last index where action is Task
#         last_task_index = None
#         for i in reversed(range(len(dc_ml))):
#             memory = dc_ml[i]
#             if isinstance(memory, Task):
#                 last_task_index = i
#                 break

#         if last_task_index is None:
#             # No Task found; include only Task if any
#             for memory in dc_ml:
#                 if isinstance(memory, Task):
#                     memory_block.append(memory)
#         else:
#             memory_block.append(dc_ml[0]) # Keep the user_request memory
            
#             # For indices before last_task_index, include only Task
#             for i in range(1, last_task_index):
#                 memory = dc_ml[i]
#                 if isinstance(memory, Task):
#                     memory_block.append(memory)
#                 elif isinstance(memory, Critic):
#                     memory_block.append(memory)
#             for memory in dc_ml[last_task_index:]:
#                 if not isinstance(memory, (Critic,
#                                            Message,
#                                            Classification, 
#                                            LocalizationFinish)):  
#                     if isinstance(memory, IPythonRun):
#                         if 'localization(' not in memory.code:
#                             memory_block.append(memory)
#                     else:
#                         memory_block.append(memory)
#     return memory_block

def execution_memory_rtve(memory_list: list, summarize_all_steps=False) -> list | None:
    '''
    Retrieve the memory from the state.history for execution without user request.
    
    Input: memory_list: All the memory.
    output: retrieved memory block.
    
    For intermediate steps, the memory should only contain:
    - Keep the first memory. # FIXME: I assume the first memory is userrequest, for multi-turns, we need to update this.
    - Keep the last Task and all memory after it except the classification memory.
    - For prior memory before the last Task, only keep those where memory is Task.
    - For the final step (Agent finished all the tasks), the memory should contain all the detailed memory execpt Classification & Critic.
    '''
    memory_block = []
    dc_ml = copy.deepcopy(memory_list)

    # If all the tasks are finished and the agent is asked to summarize all the steps
    if summarize_all_steps:
        memory_block = dc_ml
    else:
        for i in range(len(dc_ml)):
            memory = dc_ml[i]
            if not isinstance(memory, (Classification)):  
                memory_block.append(memory)
    return memory_block



def classification_memory_rtve(memory_list: list) -> list | None:
    '''
    Retrieve the memory from the state.history for execution without user request.
    
    Input: memory_list: All the memory.
    output: retrieved memory block.
    
    - Only contain the last Task.
    '''
    memory_block = []
    dc_ml = copy.deepcopy(memory_list)

    # Find the last index where action is Task
    last_task_index = None
    for i in reversed(range(len(dc_ml))):
        memory = dc_ml[i]
        if isinstance(memory, Task):
            last_task_index = i
            break

    memory_block.append(dc_ml[last_task_index])        
    return memory_block

def localization_memory_rtve(memory_list: list) -> list | None:
    '''
    Retrieve the memory from localization_memory_block, delete the Message memory.
    '''
    return [item for item in memory_list if item.__class__.__name__ != "Message"]

def retrieve_memory_further(memory_block: list, good_news=False) -> list | None:
    '''
    if the current context is too long, we need to delete some unimportant memory.
    
    Input: current memory_block.
    output: New memory block without unimportant unimportant memory.
    
    - The memory after the last AgentTaskAction should be deleted from the beginning. (It will stop deletion if only one memory block remains)
    '''
    dc_mb = copy.deepcopy(memory_block)
    
    if not good_news:
        for i in range(len(dc_mb) - 1, 0, -1): 
            if isinstance(dc_mb[i][0], Task):
                if i + 2 == len(dc_mb):  # Stop deletion if only one memory block remains
                    logger.info("Only one memory block remains after the last AgentTaskAction, stopping deletion.")
                    break
                if i + 1 < len(dc_mb): # Ensure there is a memory block to delete
                    logger.info(f"Message is too long, delete the memory: {dc_mb[i + 1]}")
                    del dc_mb[i + 1]
                break
    return dc_mb


def get_gpu_memory(ratio):
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free', '--format=csv,nounits,noheader'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    if result.returncode != 0:
        print("Failed to run nvidia-smi command")
        return False

    output = result.stdout.strip()
    for i, line in enumerate(output.split('\n')):
        total, used, free = map(int, line.split(', '))
        free_ratio = free / total
        
        print(f"GPU {i}: Total Memory: {total} MB, Used Memory: {used} MB, Free Memory: {free} MB, Free Ratio: {free_ratio:.2%}")
        
        if free_ratio < ratio:
            return False

    return True

def extract_and_reformat_summary(input_string):
    patterns = {
        "new_files": r"<new_files>(.*?)</new_files>",
        "new_code": r"<new_code>(.*?)</new_code>",
    }
    
    extracted_content = {key: "" for key in patterns}
    
    for key, pattern in patterns.items():
        match = re.search(pattern, input_string, re.DOTALL)
        if match:
            extracted_content[key] = match.group(1).strip()
    
    result_parts = []
    if extracted_content["new_files"]:
        result_parts.append(f"New Files generated while trying to finish last task:\n{extracted_content['new_files']}")
    if extracted_content["new_code"]:
        result_parts.append(f"New Code generated while trying to finish last task:\n{extracted_content['new_code']}")
    result_string = "\n\n".join(result_parts)
    return result_string

    