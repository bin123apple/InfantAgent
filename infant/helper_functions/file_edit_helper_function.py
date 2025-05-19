import os
import traceback
from infant.config import config
from infant.agent.parser import parse
from infant.computer.computer import Computer
from infant.llm.llm_api_base import LLM_API_BASED
from infant.agent.memory.memory import IPythonRun
from infant.util.logger import infant_logger as logger

async def line_drift_correction(memory: IPythonRun, computer: Computer) -> str:
    '''
    fix the line drift problem with in the edit_file() function
    '''
    try:
        fe_parameter = config.get_litellm_params(overrides = config.fe_llm)
        fe_llm = LLM_API_BASED(fe_parameter)
        iteration_times = 0
        code = memory.code
        result = memory.result
        logger.info(f'Error message: {result}')
        description = (
            f"edit_file(file_name: str, start_line: int, start_str: str, end_line: int, end_str: str, content: str): "
            "Edits the specified file by replacing the content between start and end lines with the new content. "
            "file_name: Name of the file. start_line: Starting line number. "
            "start_str: String content in Starting line. end_line: Ending line number. "
            "end_str: String content in Ending line. content: New content to replace."
        )
        example = '''USER:
Observation:
[File: /workspace/app.py (10 lines total after edit)]
1|from flask import Flask
2|app = Flask(__name__)
3|
4|@app.route('/')
5|def index():
6|    numbers = list(range(1, 11))
7|    return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'
8|
9|if __name__ == '__main__':
10|    app.run(port=5000)
[File updated. Please review the changes and make sure they are correct (correct indentation, no duplicate lines, etc). Edit the file again if necessary.]

ASSISTANT:
Let's add the print() statement again to confirm the server is running correctly.
<execute_ipython>
edit_file(file_name= 'app.py', start_line=6, start_str='    numbers = list(range(1, 11))', end_line=6, end_str:'    numbers = list(range(1, 11))', content: '    numbers = list(range(1, 11))\n    print("Server is running on port 5000...")')
</execute_ipython>

USER:
Observation:
[File: /workspace/app.py (10 lines total after edit)]
1|from flask import Flask
2|app = Flask(__name__)
3|
4|@app.route('/')
5|def index():
6|    numbers = list(range(1, 11))
7|    print("Server is running on port 5000...")
8|    return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'
9|
10|if __name__ == '__main__':
11|    app.run(port=5000)
[File updated. Please review the changes and make sure they are correct (correct indentation, no duplicate lines, etc). Edit the file again if necessary.]'''

        initial_question = (
                            f"I am using a function to edit a file: \n{description}\n"
                            f"Here is an example of the function call: \n{example}\n"
                            f"Below is the command I am running, \n{code}\n, but it seems to contain some errors. " 
                            f"Here is the detailed error message: \n{result}\n"
                            "Please help me correct the command so that I can edit the file at the right location. "
                            "You should put the new command in the <execute_ipython>...</execute_ipython> tag."
        )
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": initial_question}
                ]
            }
        ]
        while iteration_times < 3:
            iteration_times += 1
            answer, _ = fe_llm.completion(messages=messages,stop=['</execute_ipython>'])
            logger.info(f"{iteration_times} TURN in line_drift_correction. LLM result: {answer}")
            ipython_memory = parse(answer)
            message = {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": answer}
                ]
            }
            messages.append(message)
            execution_result = await computer.run_ipython(ipython_memory)
            logger.info(f"{iteration_times} TURN in line_drift_correction. Execution result: {execution_result}")
            message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": execution_result}
                ]
            }
            if "Here is the code that you are trying to modified:" in execution_result:
                messages.append(message)
            else:
                return execution_result, ipython_memory.code
    except Exception as e:
        output = traceback.format_exc()
        logger.info(output)
    return memory.result, memory.code