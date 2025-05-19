import os
import json
import shutil
from infant.agent.memory.memory import (
    Analysis,
    Userrequest,
    Message,
    Task,
    CmdRun,
    IPythonRun,
    TaskFinish,
    Finish,
)


def save_to_dataset(memory_list, log_folder, task_file_name="dataset.json"):
    """
    Save memory list to a JSON file in the `dataset` folder under the InfantAI directory.
    Optionally move the log_folder into the dataset folder.

    Args:
        memory_list (list): A list of dictionaries to save.
        task_file_name (str): The JSON file name (default is "dataset.json").
        log_folder (str, optional): The path to the log folder to move into the dataset directory.
    """

    # Step 1: Find the InfantAI directory
    current_dir = os.getcwd()
    while not current_dir.endswith("InfantAI") and os.path.dirname(current_dir) != current_dir:
        current_dir = os.path.dirname(current_dir)

    if not current_dir.endswith("InfantAI"):
        raise FileNotFoundError("InfantAI directory not found in the current path hierarchy.")

    # Step 2: Ensure the dataset folder exists
    dataset_dir = os.path.join(current_dir, "dataset")
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir)

    # Step 3: Move the log_folder into the dataset directory if it exists
    if log_folder and os.path.exists(log_folder):
        dest_log_folder = os.path.join(dataset_dir, os.path.basename(log_folder))
        shutil.move(log_folder, dest_log_folder)
        print(f"Log folder moved to: {dest_log_folder}")

    # Step 4: Construct the full path for the dataset file
    task_file_path = os.path.join(dataset_dir, task_file_name)

    # Step 5: Read existing data from the JSON file
    dataset = []
    if os.path.exists(task_file_path):
        with open(task_file_path, 'r', encoding='utf-8') as f:
            try:
                dataset = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error reading JSON file: {e}. Starting with an empty dataset.")

    # Step 6: Append the new memory list
    dialogue = memory_list_to_dialogue(memory_list)
    dataset.append(dialogue)

    # Step 7: Save the updated data back to the JSON file
    with open(task_file_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)

    print(f"Data successfully saved to {task_file_path}")
    

def memory_list_to_dialogue(memory_list):
    """
    Convert a memory list object to a dialogue.
    
    Args:
        memory list (object): A memory list object to convert.
    
    Returns:
        list[dict]: A dialogue representation of the memory list object.
    """
    dialogue = []
    for memory in memory_list:
        if isinstance(memory, CmdRun):
            dialogue.append({'role': 'user' if memory.source == 'user' else 'assistant',
                            'content': f'{memory.thought}\n<execute_bash>\n{memory.command}\n</execute_bash>'})
        elif isinstance(memory, Message):
            dialogue.append({'role': 'user' if memory.source == 'user' else 'assistant',
                            'content': memory.content})
        elif isinstance(memory, TaskFinish):
            dialogue.append({'role': 'user' if memory.source == 'user' else 'assistant',
                            'content': f'{memory.thought}<task_finish>exit</task_finish>'})
        elif isinstance(memory, Userrequest):
            dialogue.append({'role': 'user',
                            'content': memory.content})
        elif isinstance(memory, IPythonRun):
            dialogue.append({'role': 'user' if memory.source == 'user' else 'assistant',
                            'content': f'{memory.thought}\n<execute_ipython>\n{memory.code}\n</execute_ipython>'})
        elif isinstance(memory, Analysis):
            dialogue.append({'role': 'assistant',
                            'content': f'<analysis>{memory.analysis}</analysis>'})
        elif isinstance(memory, Task):
            if memory.target is not None:
                dialogue.append({'role': 'assistant',
                    'content': f'{memory.thought}<task>{memory.task}<target>{memory.target}</target></task>'})
            else:
                dialogue.append({'role': 'assistant',
                                'content': f'{memory.thought}<task>{memory.task}</task>'})
        elif isinstance(memory, Finish):
            dialogue.append({'role': 'assistant',
                            'content': f'{memory.thought}<finish>exit</finish>'})
        if hasattr(memory, 'result') and memory.result is not None:
            dialogue.append({'role': 'user',
                            'content': memory.result})
    return dialogue

        