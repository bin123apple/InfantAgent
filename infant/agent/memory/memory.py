from dataclasses import dataclass
from typing import ClassVar

memory_list = []

@dataclass
class Memory:
    runnable: ClassVar[bool] = False
    output = None # output of the command, only for runnable commands
    
    def __init__(self):
        self.source: str = ''  # agent or user

    def __str__(self) -> str:
        raise NotImplementedError("Subclasses must implement __str__")


### Runnable Commands

@dataclass
class CmdRun(Memory):
    command: str
    background: bool = False
    thought: str = ''
    special_type: str = ''
    action: str = 'run_command'
    runnable: ClassVar[bool] = True
    result: str | None = None
    images: list[str] | None = None
    
    def __str__(self) -> str:
        ret = '**CmdRun**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'COMMAND:\n{self.command}'
        if self.result:
            ret += f'\nEXECUTION RESULT:\n{self.result}'
        return ret
  
@dataclass
class CmdKill(Memory):
    command_id: int
    thought: str = ''
    action: str = 'cmd_kill'
    special_type: str = ''
    runnable: ClassVar[bool] = True
    result: str | None = None
    images: list[str] | None = None

    def __str__(self) -> str:
        ret = f'**CmdKill**\n{self.command_id}'
        if self.result:
            ret = f'EXECUTION RESULT:\n{self.result}'
        return ret

@dataclass
class IPythonRun(Memory):
    code: str
    thought: str = ''
    action: str = 'run_ipython'
    kernel_init_code: str = ''  # code to run in the kernel (if the kernel is restarted)
    runnable: ClassVar[bool] = True
    special_type: str = ''  # e.g., 'visual_grounding' for visual grounding
    result: str | None = None
    images: list[str] | None = None

    def __str__(self) -> str:
        ret = '**IPythonRun**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'command:\n{self.code}'
        if self.result:
            ret += f'\nEXECUTION RESULT:\n{self.result}'
        if self.special_type:
            ret += f'\nSPECIAL TYPE: {self.special_type}'
        return ret

@dataclass
class BrowseURL(Memory):
    url: str
    thought: str = ''
    action: str = 'browse'
    runnable: ClassVar[bool] = True
    result: str | None = None

    def __str__(self) -> str:
        ret = '**BrowseURL**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'URL: {self.url}'
        if self.result:
            ret = f'EXECUTION RESULT:\n{self.result}'
        return ret

@dataclass
class BrowseInteractive(Memory):
    browser_actions: str
    thought: str = ''
    browsergym_send_msg_to_user: str = ''
    action: str = 'browse_interactive'
    runnable: ClassVar[bool] = True
    result: str | None = None

    def __str__(self) -> str:
        ret = '**BrowseInteractive**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'BROWSER_ACTIONS: {self.browser_actions}'
        if self.result:
            ret += f'\nEXECUTION RESULT:\n{self.result}'
        return ret
    
@dataclass
class FileRead(Memory):
    """
    Reads a file from a given path.
    Can be set to read specific lines using start and end
    Default lines 0:-1 (whole file)
    """
    path: str
    start: int = 0
    end: int = -1
    thought: str = ''
    action: str = 'read'
    runnable: ClassVar[bool] = True
    result: str | None = None

    def __str__(self) -> str:
        ret = '**File Read**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'Reading file: {self.path}. Lines: {self.start}-{self.end}.'
        if self.result:
            ret += f'\nEXECUTION RESULT:\n{self.result}'
        return ret

@dataclass
class FileWrite(Memory):
    path: str
    content: str
    start: int = 0
    end: int = -1
    thought: str = ''
    action: str = 'write'
    runnable: ClassVar[bool] = True
    result: str | None = None

    def __str__(self) -> str:
        ret = '**File write**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'Modifying file: {self.path}. The new content: {self.content} will be written into lines {self.start}-{self.end}.'
        if self.result:
            ret += f'\nEXECUTION RESULT:\n{self.result}'
        return ret
    


### NOT Runnable Commands

@dataclass
class Classification(Memory):
    cmd_set: list
    thought: str = ''
    
    def __str__(self) -> str:
        ret = '**Classification**\n'
        for idx, cmd in enumerate(self.cmd_set, start=1): 
            ret += f'{idx}. {cmd}\n'
        return ret


@dataclass
class Analysis(Memory):
    analysis: str
    action: str = "analysis"

    def __str__(self) -> str:
        ret = '**Analysis**\n'
        ret += f'{self.analysis}'
        return ret
    
@dataclass
class Task(Memory):
    task: str 
    summary: str = ''
    thought: str = ''
    target: str | None = None
    action: str ='task'

    def __str__(self) -> str:
        ret = '**Task**\n'
        if self.task:
            ret += f'THOUGHT: {self.thought}\n'
            ret += f'TASK:\n{self.task}\n'
            if self.target:
                ret += f'TARGET:\n{self.target}'
        return ret
@dataclass
class Userrequest(Memory):
    text: str 
    images: list[str] | None = None
    mandatory_standards: str | None = None
    action: str = 'user_request'
    source = 'user'    

    def __str__(self) -> str:
        ret = f'**User Request**\n'
        ret += f'CONTENT: {self.text}'
        if self.mandatory_standards:
            ret += f'MANDATORY STANDARDS: {self.mandatory_standards}'
        return ret

@dataclass
class Message(Memory):
    thought: str
    wait_for_response: bool = False
    action: str = 'message'

    def __str__(self) -> str:
        ret = f'**Message** (source={self.source})\n'
        ret += f'CONTENT: {self.thought}'
        return ret

@dataclass
class Finish(Memory):
    thought: str = ''
    action: str = 'finish'
    
    def __str__(self) -> str:
        ret = '**Finish**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        return ret
    
@dataclass
class TaskFinish(Memory):
    thought: str = ''
    action: str = 'task_finish'
    
    def __str__(self) -> str:
        ret = '**Task Finish**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        return ret
    
@dataclass
class LocalizationFinish(Memory):
    thought: str = ''
    coordination = ''
    action: str = 'localization_finish'
    
    def __str__(self) -> str:
        ret = '**Localization Finish**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        if self.coordination:
            ret += f'COORDINATION: {self.coordination}\n'
        return ret
    