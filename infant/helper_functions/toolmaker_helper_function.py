import os
import traceback
from infant.config import config
from infant.agent.parser import parse
from infant.computer.computer import Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.agent.memory.memory import IPythonRun
from infant.util.logger import infant_logger as logger

# TODO: We need to write a unittest for this
async def make_new_tool(memory: IPythonRun) -> str:
    '''
    Make a new tool based on the request from the Agent
    Add the created tool to the toolsets and update the memory.result.
    '''
    try:
        tm_parameter = config.get_litellm_params(overrides = config.tm_llm)
        tm_llm = LLM_API_BASED(tm_parameter)
        code: str = memory.code
        result = memory.result
        logger.info(f'Error message: {result}')

        # TODO: Extract functionality/function_name/function_inputs/function_outputs
        # from the code: str = memory.code
        
        example = '''USER:
I need a function that can create a new sheet in an existing Excel file.

Functionality:  
- Open an existing Excel file.  
- Create a new sheet with the specified name.  
- Save the updated Excel file.  
- If the sheet already exists, raise a ValueError.  

Function name: create_excel_page  
Input: file_name (str), page_name (str)  
Output: None  

ASSISTANT:
Here is the complete function wrapped inside the <tool>...</tool> tag:

<tool>
import openpyxl

def create_excel_page(file_name: str, page_name: str) -> None:
    """
    Create a new sheet in the given Excel file.

    Args:
        file_name (str): Path to the Excel file.
        page_name (str): Name of the new sheet to be created.

    Returns:
        None

    Raises:
        ValueError: If the sheet already exists.
    """
    wb = openpyxl.load_workbook(file_name)
    if page_name in wb.sheetnames:
        raise ValueError(f"Sheet '{page_name}' already exists.")
    wb.create_sheet(title=page_name)
    wb.save(file_name)
</tool>'''

        initial_question = (
                            f"Please help me to write a new python function based on the following instruction: "
                            f"The function should provide the following functionality. \n{functionality}\n"
                            f"The name of the function should be: \n{function_name}\n" 
                            f"The input of the function should be: \n{function_inputs}\n"
                            f"The output of the function should be: \n{function_outputs}\n"
                            "Please verify your function thoroughly. For example, write unit tests to validate its behavior. "
                            "Finally, please only provide the complete function and wrap it inside the <tool>...</tool> tag."
                            f"Here is an example: \n{example}\n"
        )
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": initial_question}
                ]
            }
        ]
        answer, _ = tm_llm.completion(messages=messages,stop=['</tool>'])
        tool = parse(answer)
        new_tool = f'The tool named {function_name} is created, If you encounter any issues during use, please let me know.'
        memory.result = tool
        # TODO: read papers (toolmaker/osworld top grade) and check how they create the tool, is there any feedback?
    except Exception as e:
        output = traceback.format_exc()
        logger.info(output)
    return memory.result, memory.code