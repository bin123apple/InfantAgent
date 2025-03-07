from infant.agent.memory.memory import ( 
    Task,
    Finish, 
    Critic,
    Memory, 
    Message, 
    Analysis,
    Summarize, 
    TaskFinish, 
    IPythonRun,
    Userrequest,
    Classification, 
    LocalizationFinish,
)
from infant.util.logger import infant_logger as logger
from infant.prompt.reasoning_prompt import reasoning_task_end_prompt_avoid_repetition

def handle_reasoning_repetition(memory_list, max_repetition):
    """
    Handles the repetition of reasoning outputs in the reasoning phase.
    If the number of repeated outputs exceeds a certain threshold, it updates the reasoning_task_end_prompt to encourage new ideas.
    """
    # define the threshold for repeated analysis  
    analysis_repetition_threshold = max_repetition
    analysis_count = 0

    # reverse iterate through the memory list to count the number of repeated analysis outputs
    for mem in reversed(memory_list):
        if isinstance(mem, TaskFinish):
            break
        # count the number of repeated analysis outputs
        if isinstance(mem, Analysis):
            analysis_count += 1

    # If the number of repeated analysis outputs exceeds the threshold, update the reasoning_task_end_prompt
    if analysis_count > analysis_repetition_threshold:
        new_prompt = reasoning_task_end_prompt_avoid_repetition
        logger.info(
            f"Reasoning repetition detected: {analysis_count} analysis messages since last TaskFinish. "
            f"Updating reasoning_task_end_prompt."
        )
        return new_prompt
    return None


def check_accumulated_cost(current_cost, max_cost):
    """
    Check if the accumulated cost exceeds the maximum allowed cost.
    """
    if current_cost > max_cost:
        logger.info(
            f"Accumulated cost {current_cost} exceeds maximum allowed cost {max_cost}. "
            f"Resetting memory."
        )
        return True
    return False

