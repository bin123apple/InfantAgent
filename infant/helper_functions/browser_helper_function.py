from __future__ import annotations

import re
import ast
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from infant.agent.agent import Agent
from infant.computer.computer import Computer
from infant.agent.memory.memory import Memory, IPythonRun
from infant.util.debug import print_messages
from infant.util.logger import infant_logger as logger


GET_STATE_CODE = """state = await context.get_state()
print(state)
"""

OPEN_BROWSER_CODE = """import subprocess

with open("/tmp/log.log", "w") as log_file:
    subprocess.Popen(
        ["google-chrome", "--remote-debugging-port=9222"],
        stdout=log_file, stderr=subprocess.STDOUT,
        close_fds=True
    )
    
config = BrowserConfig(
    headless=False,
    chrome_instance_path='/usr/bin/google-chrome',
    cdp_url="http://127.0.0.1:9222"
)

browser = Browser(config)
context = await browser.new_context()
EOL"""

LOCALIZATION_SYSTEM_PROMPT_BROWSER = '''I want to click on {item_to_click} with the mouse. {description}
Please help me determine the exact DOM element node that I need to click on. 
I will provide you with:
1. A screenshot of my computer screen, where all DOMElementNodes will be highlighted and numbered.
2. Detailed information about the current page, including the index of each DOMElementNode and its corresponding HTML code.
'''

LOCALIZATION_USER_INITIAL_PROMPT_BROWSER = '''I want to click on {item_to_click} with. {description} 
Please help me determine its **EXACT** element node index.
I have provided you with the current screenshot, where all DOMElementNodes will be highlighted and numbered.
The detailed information about the current page, including the index of each DOMElementNode and its corresponding HTML code is shown below:
Tabs information: {tabs}
URL: {url}
Title: {title}
element tree: {element_tree}
pixels above current screen: {pixels_above}
pixels below current screen: {pixels_below}
DOMElementNodes:
{selector_map}
Please tell me the **EXACT** element node index that I should click, if the {item_to_click} is not number, please return None
You should put your final answer in <index>...</index> tag. For example, your can return <index>5</index> or <index>None</index>'''.strip()

DETECT_DROPDOWN = '''Detected a dropdown menu. Please carefully observe the contents of these dropdown menus. If needed, use the function `select_dropdown_option(selector_index: int, option: int)` to select your desired option.'''

def extract_parameter_values(signature):
    # 提取圆括号内的内容
    match = re.search(r'\((.*?)\)', signature)
    if not match:
        return {}
    content = match.group(1).strip()
    
    # 判断是否包含 '='，决定使用哪种解析方式
    if '=' in content:
        # 处理关键字参数形式，如 index=1, option=2
        pairs = re.findall(r'\s*(\w+)\s*=\s*([^,]+)', content)
        result = {}
        for key, value in pairs:
            value = value.strip()
            # 尝试转换为数字类型
            if value.isdigit():
                result[key] = int(value)
            else:
                try:
                    result[key] = float(value)
                except ValueError:
                    result[key] = value
        return result
    else:
        # 处理位置参数形式，如 1,2
        values = [v.strip() for v in content.split(',') if v.strip()]
        converted = []
        for value in values:
            if value.isdigit():
                converted.append(int(value))
            else:
                try:
                    converted.append(float(value))
                except ValueError:
                    converted.append(value)
        # 默认按照顺序映射到 index 和 option
        result = {}
        if len(converted) >= 1:
            result['index'] = converted[0]
        if len(converted) >= 2:
            result['option'] = converted[1]
        return result

async def check_dropdown_options(agent: Agent, cmd: str, interactive_elements: list):
    result = ''
    dropdown_dict = None
    if cmd == 'web_browse': 
        get_state = IPythonRun(code='await context.get_state()')
        await agent.computer.run_ipython(get_state)
        get_dropdown = IPythonRun(code=f'dropdowns = await context.get_all_dropdown_options({interactive_elements})\nprint(dropdowns)')
        dropdowns = await agent.computer.run_ipython(get_dropdown)
        if "Use the exact text string in select_dropdown_option" in dropdowns:
            dropdown_dict = parse_dropdown_options(dropdowns)
            prefix = "Use the exact text string in select_dropdown_option"
            dropdowns = dropdowns.replace(prefix, "").replace('(exit code=0)','').strip()
            result += f'{DETECT_DROPDOWN}:\n{dropdowns}'
        remove_highlight = IPythonRun(code='await context.remove_highlights()')
        await agent.computer.run_ipython(remove_highlight)    
    return result, dropdown_dict

def parse_dropdown_options(text):
    # 去掉前缀并strip
    prefix = "Use the exact text string in select_dropdown_option"
    text = text.replace(prefix, "").replace('(exit code=0)','').strip()
    
    result = {}
    current_key = None
    
    # 按行分割
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 检查是否为 Selector index 开头的行
        if line.startswith("Selector index"):
            # 例如 "Selector index 18 dropdown options:" 分割后得到 ["Selector", "index", "18", ...]
            parts = line.split()
            if len(parts) >= 3:
                current_key = parts[2]
                result[current_key] = {}
        else:
            # 处理选项行，例如： 0: text="New York\nCity in New York State"
            if ": text=" in line:
                key_part, text_part = line.split(": text=", 1)
                option_key = key_part.strip()
                # 移除双引号
                if text_part.startswith('"') and text_part.endswith('"'):
                    value = text_part[1:-1]
                else:
                    value = text_part
                if current_key is not None:
                    result[current_key][option_key] = value
    return result

def convert_web_browse_commands(memory: IPythonRun, finish_switch: bool, dropdown_dict: dict) -> Memory:
    if memory.code == 'open_browser()':
        memory.code = OPEN_BROWSER_CODE
        return memory

    if any(cmd in memory.code for cmd in ['type_text', 'press_key', 
                                          'press_key_combination', 
                                          'mouse_drag', 'mouse_box_select']):
        return memory
    
    if not finish_switch:
        if any(cmd in memory.code for cmd in ['mouse_left_click', 'mouse_double_click', 
                                            'mouse_right_click']):
            return memory

    if  'select_dropdown_option' in memory.code and dropdown_dict:
        dropdown_option = extract_parameter_values(memory.code) # dict
        if 'index' in dropdown_option and 'option' in dropdown_option:
            index = dropdown_option['index']
            text = dropdown_dict.get(str(index), {}).get(str(dropdown_option['option']), None)
            memory.code = f'await context.select_dropdown_option(index={index}, text="{text}")'
            return memory
    
    memory.code = f'await context.{memory.code.strip()}'
    return memory
    

def parse_browser_state(s: str) -> dict:
    # 去掉开头的 "BrowserState(" 和末尾的 ")"
    s = s.partition("BrowserState(")[1] + s.partition("BrowserState(")[2]
    prefix = "BrowserState("
    if s.startswith(prefix):
        s = s[len(prefix):]
    if s.endswith(")"):
        s = s[:-1]

    result = {}
    key = ""
    value = ""
    in_key = True
    nesting = 0  # 用于跟踪 ()、[]、{} 的嵌套层级
    i = 0
    while i < len(s):
        char = s[i]
        if in_key:
            if char == '=' and nesting == 0:
                key = key.strip()
                in_key = False
            else:
                key += char
        else:
            # 遇到嵌套符号时更新层级
            if char in "([{":
                nesting += 1
            elif char in ")]}":
                nesting -= 1

            # 当逗号位于最外层时，则认为一个属性结束
            if char == ',' and nesting == 0:
                result[key.strip()] = value.strip()
                key = ""
                value = ""
                in_key = True
                # 跳过逗号后可能的空格
                i += 1
                continue
            else:
                value += char
        i += 1

    # 最后如果还有剩余的 key-value 对也添加进去
    if key:
        result[key.strip()] = value.strip()

    return result

def parse_selector_map_string(selector_map_str: str) -> dict:
    pattern = r'(\d+):\s*(<.*?>\s*\[[^\]]+\])'
    matches = re.findall(pattern, selector_map_str)

    # 构造字典，键转换为整数
    selector_map_dict = {int(key): value for key, value in matches}
    return selector_map_dict

def get_sorted_selector_map(selector_map: dict) -> dict:
    """
    根据键（假定为数字）从小到大排序 selector_map 字典。
    """
    sorted_selector_map = ''
    for key in sorted(selector_map.keys()):
        sorted_selector_map += f'{key}: {selector_map[key]}\n'
    return sorted_selector_map.strip()

def replace_icon_desc_with_element_index(command, element_index):
    """
    Replace `icon` and `desc` parameters in the given command with `x` and `y` values.

    Args:
        command (str): Command string containing `pyautogui.click`.
        element_index (int): DOMElementNode_index

    Returns:
        str: Modified command string.
    """
    # Regular expression to find the action
    pattern = r"mouse_(left_click|double_click|move|right_click)\(.*?\)"
    match = re.search(pattern, command)
    if match:
        action = match.group(1)
    
    # # Regular expression to find `icon` and `desc` parameters
    # pattern = r"item\s*=\s*'.*?',\s*description\s*=\s*'.*?'"
    replacement = f"element_index={element_index}"

    # # Replace the matched part with element index
    # modified_command = re.sub(pattern, replacement, command)
    if action == 'left_click':
        modified_command = f"left_click_element_node({replacement})"
    elif action == 'double_click':
        modified_command = f"double_click_element_node({replacement})"
    elif action == 'right_click':
        modified_command = f"right_click_element_node({replacement})"

    return modified_command

def extract_icon_and_desc(command):
    '''
    Extract `icon` and `desc` values from the given command.
    Args:
        command (str): Command string containing `icon` and `desc`.
    Returns:
        tuple: Extracted icon and desc values as a tuple of strings.
    '''
    icon_pattern = r"item\s*=\s*'([^']*)'|item\s*=\s*\"([^\"]*)\""
    desc_pattern = r"description\s*=\s*'([^']*)'|description\s*=\s*\"([^\"]*)\""

    icon_match = re.search(icon_pattern, command, re.IGNORECASE)
    desc_match = re.search(desc_pattern, command, re.IGNORECASE)

    if icon_match or desc_match:
        icon = (icon_match.group(1) if icon_match and icon_match.group(1)
                else icon_match.group(2) if icon_match else None)
        desc = (desc_match.group(1) if desc_match and desc_match.group(1)
                else desc_match.group(2) if desc_match else None)
        return icon, desc

    positional_pattern = r"\(\s*(['\"])(?P<icon>.*?)\1\s*,\s*(['\"])(?P<desc>.*?)\3"
    pos_match = re.search(positional_pattern, command, re.DOTALL)
    if pos_match:
        icon = pos_match.group("icon")
        desc = pos_match.group("desc")
        return icon, desc

    return None, None

def extract_index(resp):
    if f'<index>' in resp and f'</index>' not in resp: # BrowseURL, BrowseInteractive
        resp += f'</index>'
    index = re.search(r'<index>(.*?)</index>', resp, re.DOTALL)
    if index:
        index = index.group(1).strip()    
        if index is None or index == "None" or index == "none":
            return None
        try:
            return int(index)
        except ValueError:
            return None
    else:
        return None

async def localization_browser(agent: Agent, memory: Memory, interactive_elements: list):
    '''
    Localize the image description to the coordinate for accurate mouse click.
    Args:
        computer (Computer): The computer object. For some basic operations.
        memory (Memory): The memory object. The memory object to be updated.
    Returns:
        Memory: The updated memory object.
    '''
    computer = agent.computer
    finish_switch = False
    if isinstance(memory, IPythonRun) and memory.code:
        pattern = r"mouse_(?:left_click|double_click|move|right_click)\(.*?\)"
        match = re.search(pattern, memory.code)
        if match:
            logger.info(f"=========Start Browser localization=========")
            # Take a screenshot
            icon, desc = extract_icon_and_desc(memory.code)
            if icon is None or desc is None:
                logger.info(f"=========End Browser localization=========")
                return memory, finish_switch, interactive_elements
            logger.info(f"Icon: {icon}, Desc: {desc}")
            get_state_action = IPythonRun(code=GET_STATE_CODE)
            browser_state = await computer.run_ipython(get_state_action)
            
            remove_highlight_action = IPythonRun(code='await context.remove_highlights()')
            await computer.run_ipython(remove_highlight_action)
            
            # Find the coordination
            element_index = await image_description_to_element_index(agent, 
                                                                     computer, icon, desc, browser_state)
            logger.info(f"Element Index: {element_index}")
            
            try: 
                if isinstance(element_index, int):
                    interactive_elements.append(element_index)
                    memory.code = replace_icon_desc_with_element_index(memory.code, element_index) # replace the image description with the coordinate
                    logger.info(f"Mouse clicked at Element Index: ({element_index})")
                    logger.info(f"=========End Browser localization=========")
                    finish_switch = True
                    return memory, finish_switch, interactive_elements
                else:
                    logger.error("Element Index is not a valid int.")
            except (SyntaxError, ValueError) as e:
                logger.error(f"Failed to parse Element Index: {element_index}. Error: {e}")  
    logger.info(f"=========End Browser localization=========")
    return memory, finish_switch, interactive_elements

async def image_description_to_element_index(agent: Agent, computer: Computer, 
                                             icon: str, desc: str, browser_state: str):
    """
    Convert the image description to coordinate for accurate mouse click.
    """
    parsed_browser_state: dict = parse_browser_state(browser_state)
    # logger.info(f"Browser State: {parsed_browser_state}")
    # Initialize the localization memory block
    byte_image = parsed_browser_state.get('screenshot', None)
    selector_map_str = parsed_browser_state.get('selector_map', "")
    selector_map_dict = parse_selector_map_string(selector_map_str)
    # selector_map_dict = ast.literal_eval(selector_map_str)
    tabs = parsed_browser_state.get('tabs', [])
    url = parsed_browser_state.get('url', "")
    title = parsed_browser_state.get('title', "")
    element_tree = parsed_browser_state.get('element_tree', {})
    pixels_above = parsed_browser_state.get('pixels_above', 0)
    pixels_below = parsed_browser_state.get('pixels_below', 0)
    sorted_selector_map = get_sorted_selector_map(selector_map_dict)
    
    
    messages = []
    messages.append({'role': 'system', 'content': LOCALIZATION_SYSTEM_PROMPT_BROWSER.format(item_to_click=icon, description=desc)})
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": LOCALIZATION_USER_INITIAL_PROMPT_BROWSER.format(item_to_click=icon, description=desc, 
                                                                tabs=tabs, url=url, title=title, element_tree=element_tree,
                                                                pixels_above=pixels_above, pixels_below=pixels_below,
                                                                selector_map=sorted_selector_map)
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{byte_image}",
                    "detail": "high"
                }
            }
        ]
    })
    try:
        # print_messages(messages, "image_description_to_element_index")
        response,_ = agent.llm.completion(messages=messages, stop=['</index>'])
        logger.info(f"Response in browwser helper function: {response}")
        element_index = extract_index(response)
        return element_index
    except Exception as e:
        logger.error("Failed to call" + computer.model + ", Error: " + str(e))

    