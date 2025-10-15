from infant.agent.memory.memory import Analysis, TaskFinish
from infant.util.logger import infant_logger as logger
from infant.prompt.planning_prompt import planning_task_end_prompt_avoid_repetition

def handle_planning_repetition(memory_list, max_repetition):
    """
    Handles the repetition of planning outputs in the planning phase.
    If the number of repeated outputs exceeds a certain threshold, it updates the planning_task_end_prompt to encourage new ideas.
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

    # If the number of repeated analysis outputs exceeds the threshold, update the planning_task_end_prompt
    if analysis_count > analysis_repetition_threshold:
        new_prompt = planning_task_end_prompt_avoid_repetition
        logger.info(
            f"planning repetition detected: {analysis_count} analysis messages since last TaskFinish. "
            f"Updating planning_task_end_prompt."
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

class NeedUserInput(Exception):
    """内部用于标记：Agent 需要用户输入，先中断并返回给前端。"""
    def __init__(self, prompt: str):
        self.prompt = prompt