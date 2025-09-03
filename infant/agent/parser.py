import re
from infant.agent.memory.memory import (
    Memory,
    Analysis,
    Message,
    Task,
    CmdRun,
    IPythonRun,
    BrowseURL,
    Finish,
    TaskFinish,
    Classification,
    LocalizationFinish
)
from infant.util.logger import infant_logger as logger

def parse(response: str) -> Memory:
    resp_completion = response_completion(response)
    return parse_response(resp_completion)

def response_completion(resp) -> str:
    for lang in ['bash', 'ipython']: # IPythonRun, CmdRun
        if f'<execute_{lang}>' in resp and f'</execute_{lang}>' not in resp:
            resp += f'</execute_{lang}>'
    if f'<browse>' in resp and f'</browse>' not in resp: # BrowseURL, BrowseInteractive
        resp += f'</browse>'
    if f'<task>' in resp and f'</task>' not in resp: # task
        resp += f'</task>'
    if f'<analysis>' in resp and f'</analysis>' not in resp: # Analysis
        resp += f'</analysis>'
    for tag in ['potential_issue', 'git_diff', 'key_steps', 'reason', ]: # Summarize
        if f'<{tag}>' in resp and f'</{tag}>' not in resp:
            resp += f'</{tag}>' 
    if f'<mandatory_standards>' in resp and f'</mandatory_standards>' not in resp: # add mandatory standards to Userrequest
        resp += f'</mandatory_standards>'
    if f'<clf_task>' in resp and f'</clf_task>' not in resp: # Classification
        resp += f'</clf_task>'
    if f'<finish>' in resp and f'</finish>' not in resp: # Finish
        resp += f'</finish>'
    if f'<task_finish>' in resp and f'</task_finish>' not in resp: # TaskFinish
        resp += f'</task_finish>'
    if f'<loca_finish>' in resp and f'</loca_finish>' not in resp: # LocalizationFinish
        resp += f'</loca_finish>'
    if f'<tool>' in resp and f'</tool>' not in resp:
        resp += f'</tool>'
    return resp

def parse_response(resp: str) -> str:
    
    # parse user input
    # FIXME: Implement a function to convert the user input to Userrequest class 
    
    # parse summary
    summary = {}
    tags = ['key_steps', 'reason']
    for tag in tags:
        match = re.search(rf'<{tag}>(.*?)</{tag}>', resp, re.DOTALL)
        if match:
            summary[tag] = match.group(1).strip()
    if bool(summary):
        memory = Summarize(summary=summary)
        memory.source = 'assistant'
        return memory
    
    # parse task
    task_match = re.search(r'<task>(.*?)</task>', resp, re.DOTALL)
    target = None
    ## Check for target within the task if task is found
    if task_match:
        target_match = re.search(r'<target>(.*?)</target>', task_match.group(1), re.DOTALL)
        task_content = task_match.group(1).strip()
        
        if target_match:
            target = target_match.group(1).strip()
            task = task_content.split('<target>')[0].strip() 
        else:
            task = task_content 

        thought = resp[:task_match.start()].strip() 
        memory = Task(thought=thought, task=task, target=target)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'Task'})
        return memory
    
    # parse analysis
    analysis = re.search(r'<analysis>(.*?)</analysis>', resp, re.DOTALL)
    if analysis:
        analysis = analysis.group(1).strip()
        memory = Analysis(analysis=analysis)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'Analysis'})
        return memory
    
    # parse classification
    classification = re.search(r'<clf_task>(.*?)</clf_task>', resp, re.DOTALL)
    if classification:
        classification = classification.group(1).strip()
        cmd_set = [item.strip() for item in classification.split(',')] 
        memory = Classification(cmd_set=cmd_set)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'Classification'})
        return memory
    
    # parse mandatory standards for Userrequest
    mandatory_standards = re.search(r'<mandatory_standards>(.*?)</mandatory_standards>', resp, re.DOTALL)
    if mandatory_standards:
        mandatory_standards = mandatory_standards.group(1).strip()
        return mandatory_standards # Only for user request, it returns a mandatory standard
    
    # parse ipython run
    python_code = re.search(r'<execute_ipython>(.*?)</execute_ipython>', resp, re.DOTALL)
    if python_code:
        code_group = python_code.group(1).strip()
        thought = resp.replace(python_code.group(0), '').strip()
        memory = IPythonRun(code=code_group,thought=thought)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'IPythonRun'})
        return memory
    
    # parse bash run
    bash_command = re.search(r'<execute_bash>(.*?)</execute_bash>', resp, re.DOTALL)
    if bash_command:
        thought = resp.replace(bash_command.group(0), '').strip()
        command_group = bash_command.group(1).strip()
        memory = CmdRun(command=command_group, thought=thought)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'CmdRun'})
        return memory
    
    # parse Finish
    finish_command = re.search(r'<finish>.*</finish>', resp, re.DOTALL)
    if finish_command:
        thought = resp.replace(finish_command.group(0), '').strip()
        memory = Finish(thought=thought)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'Finish'})
        return memory
    
    # parse Task Finish
    task_finish_command = re.search(r'<task_finish>.*</task_finish>', resp, re.DOTALL)
    if task_finish_command:
        thought = resp.replace(task_finish_command.group(0), '').strip()
        memory = TaskFinish(thought=thought)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'TaskFinish'})
        return memory
    
    # parse Localization Finish
    local_finish_command = re.search(r'<loca_finish>(.*?)</loca_finish>', resp, re.DOTALL)
    if local_finish_command:
        coordination = local_finish_command.group(1).strip()
        thought = resp.replace(local_finish_command.group(0), '').strip()
        memory = LocalizationFinish(thought=thought)
        memory.source = 'assistant'
        memory.coordination = coordination 
        logger.info(memory, extra={'msg_type': 'LocalizationFinish'})
        return memory

    # parse browse
    browse_command = re.search(r'<browse>(.*)</browse>', resp, re.DOTALL)
    if browse_command:
        thought = resp.replace(browse_command.group(0), '').strip()
        url = browse_command.group(1).strip()
        memory = BrowseURL(url=url, thought=thought)
        memory.source = 'assistant'
        logger.info(memory, extra={'msg_type': 'BrowseURL'})
        return memory
    
    # Others are consider as normal message
    memory = Message(thought=resp)
    memory.source = 'assistant'
    logger.info(memory, extra={'msg_type': 'Message'})
    return memory

