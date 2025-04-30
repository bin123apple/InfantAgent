"""Script to run end-to-end evaluation on the benchmark.
Utils and basic architecture credit to https://github.com/web-arena-x/webarena/blob/main/run.py.
"""
import io
import os
import re
import sys
import time
import copy
import json
import shutil
import base64
import requests
import logging
import argparse
import datetime
import traceback
from math import sqrt
import anthropic

from tqdm import tqdm
import lib_run_single
from typing import Tuple
from vllm import LLM, SamplingParams
from desktop_env.desktop_env import DesktopEnv
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

file_handler = logging.FileHandler(
    os.path.join("logs", "normal-{:}.log".format(datetime_str)), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join("logs", "debug-{:}.log".format(datetime_str)), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)
sdebug_handler = logging.FileHandler(
    os.path.join("logs", "sdebug-{:}.log".format(datetime_str)), encoding="utf-8"
)

file_handler.setLevel(logging.INFO)
debug_handler.setLevel(logging.DEBUG)
stdout_handler.setLevel(logging.INFO)
sdebug_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
)
file_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
stdout_handler.setFormatter(formatter)
sdebug_handler.setFormatter(formatter)

stdout_handler.addFilter(logging.Filter("desktopenv"))
sdebug_handler.addFilter(logging.Filter("desktopenv"))

logger.addHandler(file_handler)
logger.addHandler(debug_handler)
logger.addHandler(stdout_handler)
logger.addHandler(sdebug_handler)
#  }}} Logger Configs #

logger = logging.getLogger("desktopenv.experiment")

CURRENT_WHOLE_IMAGE = None
CURRENT_IMAGE_RANGE = None
CURRENT_RED_POINT = None

SYS_PROMPT_IN_SCREENSHOT_OUT_CODE_ONE_COMMAND = """
You are an agent which follow my instruction and perform desktop computer tasks as instructed.
You have good knowledge of computer and good internet connection and assume your code will run on a computer for controlling the mouse and keyboard.
For each step, you will get an observation of an image, which is the screenshot of the computer screen and you will predict the action of the computer based on the image.

You are required to use `pyautogui` to perform the action grounded to the observation, but DONOT use the `pyautogui.locateCenterOnScreen` function to locate the element you want to operate with since we have no image of the element you want to operate with. DONOT USE `pyautogui.screenshot()` to make screenshot.
Return one line of python code to perform the ONE action each time. 
You need to to specify the coordinates of by yourself based on your observation of current observation, but you should be careful to ensure that the coordinates are correct.
You ONLY need to return the code inside a code block, like this:
```python
# your code here
```
Note: If you want to use the `pyautogui.click`, `pyautogui.mouseDown`, `pyautogui.moveTo` commands, replace the coordinate parameters X and Y in the original function with the target you want to click on and a descriptive text of its shape, color and position. 
If you want to use the `pyautogui.dragTo` command, use `pyautogui.mouseDown` to click on the target you want to drag and then use `pyautogui.moveTo(item: str, description: str,)` to move the mouse to the target you want to drag to and then use `pyautogui.mouseUp` to release the mouse button.
If you want to perform a right-click, please use: `pyautogui.click(item: str, description: str, button='right')` instead of `pyautogui.rightClick()`.
For example:
For pyautogui.click, you should use the following command format:
```python
pyautogui.click(
    item: str,
    description: str,
    button: str
)
```

If you want to use pyautogui.click to click on the VS Code icon, you should use the following command:
```python
pyautogui.click(
    item='vscode icon',
    description='It is located in the sidebar (Launcher) on the left side of the screen. It is the first icon from the top in the vertical arrangement. The icon has a blue background with a white folded "V"-shaped design in the center. The sidebar is aligned along the leftmost edge of the screen, adjacent to the desktop background on its right side.',
    button='left'
)
```

Instead of:
```python
pyautogui.click(x=500, y=300, button='left')
```
For `pyautogui` commands other than `pyautogui.click`, please use the normal format.
Specially, it is also allowed to return the following special code:
When you think you have to wait for some time, return ```WAIT```;
When you think the task can not be done, return ```FAIL```;
When you think the task is done, return ```DONE```.

My computer's password is 'password', feel free to use it when you need sudo rights.
First give the current screenshot and previous things we did a short reflection, then RETURN ME THE CODE OR SPECIAL CODE I ASKED FOR. NEVER EVER RETURN ME ANYTHING ELSE.
""".strip()

NOTES = '''NOTE: 
1. If you want to use the `pyautogui.click`, `pyautogui.drag`, `pyautogui.mouseDown`, `pyautogui.moveTo` commands, replace the coordinate parameters `x` and `y` in the original function with the target you want to click on and a descriptive text of its shape, color and position.
2. Some settings require restarting the application before they take effect.
3. If you are asked to browse some web pages, please ensure that the page you ultimately open meets all of the requirements.
4. Please use terminal to finish the libreoffice cal task if you can.'''

def extract_coordinates(result: list[str]):
    text = result[0].strip()

    # 如果有 <answer> 标签，就提取标签内的内容；否则就直接用 text
    answer_match = re.search(r'<answer>\s*(.*?)\s*</answer>', text, re.DOTALL)
    if answer_match:
        content = answer_match.group(1)
    else:
        content = text  

    # 按 (x, y) 形式提取
    point_match = re.search(r'\(\s*(\d+)\s*,\s*(\d+)\s*\)', content)
    if point_match:
        x, y = map(int, point_match.groups())
        return (x, y)

    # 如果是 (x1, y1, x2, y2) 形式，取中心点
    box_match = re.search(r'\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', content)
    if box_match:
        x1, y1, x2, y2 = map(int, box_match.groups())
        return ((x1 + x2)//2, (y1 + y2)//2)

    return (-1,-1)

def backup_image(image_path, mount_path, backup_dir="Backup/osworld/images"):

    # Ensure backup directory exists
    os.makedirs(backup_dir, exist_ok=True)

    # Define target path
    target_path = os.path.join(backup_dir, os.path.basename(image_path))

    # Copy the image
    shutil.copy(image_path, target_path)
    logger.info(f"Image backed up to {target_path}")
    
def localization_point(x: int, y: int)-> Tuple[Image.Image, tuple, tuple, tuple]:
    """
    This function is used to check the exact screen position of a coordinate by drawing a red dot on the screen.
    
    Args:
        x (int): The x-coordinate of the point to check.
        y (int): The y-coordinate of the point to check.
        
    Returns:
        None
    """
    global CURRENT_WHOLE_IMAGE
    global CURRENT_RED_POINT
    
    if x < 0 or x >= CURRENT_WHOLE_IMAGE.width or y < 0 or y >= CURRENT_WHOLE_IMAGE.height:
        return None, None, None, (-1,-1)
    
    # Draw a red dot on the image at the specified coordinates
    CURRENT_RED_POINT = (x, y)
    x_range = [0,CURRENT_WHOLE_IMAGE.width]
    y_range = [0,CURRENT_WHOLE_IMAGE.height]
    copy_img = CURRENT_WHOLE_IMAGE.copy()
    draw = ImageDraw.Draw(copy_img)
    dot_radius = 10
    dot_color = (255, 0, 0)
    draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill=dot_color)
    return copy_img, x_range, y_range, (x, y)

def highlight_and_save_region(center: tuple[int, int], half_size_x: int = 700, half_size_y: int = 250):
    """
    Highlight a region around the specified center point in the current image.
    """
    global CURRENT_WHOLE_IMAGE
    image = CURRENT_WHOLE_IMAGE.copy()
    width, height = image.size
    x, y = center
    left = max(0, x - half_size_x)
    top = max(0, y - half_size_y)
    right = min(width, x + half_size_x)
    bottom = min(height, y + half_size_y)
    
    if left >= right or top >= bottom:
        raise ValueError(f"Invalid region: {(left, top, right, bottom)}")
    cropped = image.crop((left, top, right, bottom))
    byte_cropped = save_image_and_convert_to_byte(cropped)
    offset = (left, top)
    return byte_cropped, offset

def clean_actions(actions):
    """
    Post-process a list of PyAutoGUI action strings, removing any
    redundant button='right' parameter from rightClick calls.
    
    Args:
        actions (List[str]): List of code strings representing PyAutoGUI calls.
    
    Returns:
        List[str]: Cleaned list of action strings.
    """
    cleaned_actions = []
    for action in actions:
        if "pyautogui.rightClick" in action:
            # Remove ", button='right'" (or with double quotes) wherever it appears
            action = re.sub(r",\s*button=['\"]right['\"]", "", action)
        elif "pyautogui.moveTo" in action:
            action = re.sub(r",\s*button=['\"][^'\"]*['\"]", "", action)
        cleaned_actions.append(action)
    
    logger.debug("Original actions: %s", actions)
    logger.debug("Cleaned actions: %s", cleaned_actions)
    return cleaned_actions

def save_image_and_convert_to_byte(img: Image.Image) -> bytes:
    '''
    Save the image with grid to intermediate folder and return the byte data of the image.
    Args:
        mount_path (str): The directory to save the intermediate results.
        img (Image): The image to be saved.
    Returns:
        bytes: The byte data of the image.
    '''
    mount_path = os.getcwd()
    os.makedirs(f'{mount_path}/intermediate_steps/', exist_ok=True) 
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{mount_path}/intermediate_steps/{timestamp}.png"
    img.save(filename)
    logger.info(f"Intermediate Image saved as: {filename}")
    with open(filename, "rb") as file:
        image_bytes = file.read()
    return image_bytes

def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')

def replace_icon_desc_with_coordinates(command: str, x: int, y: int) -> str:
    """
    Replace `item` and `description` parameters in the given command with `x` and `y` values.
    Args:
        command (str): Command string containing pyautogui.click.
        x (int): X-coordinate value.
        y (int): Y-coordinate value.
    Returns:
        str: Modified command string or a no-op move if coords are invalid.
    """
    if x == -1 or y == -1:
        return "pyautogui.moveRel(0, 0)"

    pattern = re.compile(
        r"item\s*=\s*(?P<q1>['\"])(?P<item>.*?)(?P=q1)"     
        r"(?=\s*,\s*description)\s*,\s*"
        r"description\s*=\s*(?P<q2>['\"])(?P<desc>.*?)(?P=q2)"
        r"(?=\s*(?:,|\)))",                                  
        re.IGNORECASE | re.DOTALL
    )

    def _repl(m: re.Match) -> str:
        return f"x={x}, y={y}"

    return pattern.sub(_repl, command)

def extract_icon_and_desc(command: str) -> tuple[str, str]:
    """
    Extract `item` and `description` values from the given command.
    """
    # 单引号版本：结束单引号后必须跟逗号或右括号
    single_pattern = re.compile(
        r"item\s*=\s*'(?P<item>.*?)'(?=\s*,\s*description)\s*,\s*"
        r"description\s*=\s*'(?P<desc>.*?)'(?=\s*(?:,|\)))",
        re.IGNORECASE | re.DOTALL
    )
    m = single_pattern.search(command)
    if m:
        return m.group('item'), m.group('desc')

    # 双引号版本：同理
    double_pattern = re.compile(
        r'item\s*=\s*"(?P<item>.*?)"(?=\s*,\s*description)\s*,\s*'
        r'description\s*=\s*"(?P<desc>.*?)"(?=\s*(?:,|\)))',
        re.IGNORECASE | re.DOTALL
    )
    m2 = double_pattern.search(command)
    if m2:
        return m2.group('item'), m2.group('desc')

    return None, None

def extract_coordination(command):
    """
    Extract `x` and `y` values from the given command.

    Args:
        command (str): Command string containing `localization_done` with x and y.

    Returns:
        tuple: Extracted x and y values as a tuple of integers.
    """
    # Define the regular expression pattern to extract `x` and `y`
    pattern = r"localization_done\((\d+),\s*(\d+)\)"
    match = re.search(pattern, command)

    if not match:
        logger.error("Invalid command format. Expected format: 'localization_done(x, y)'")
        return (0, 0)
    # Extract and return x and y as a tuple
    return tuple(map(int, match.groups()))

def parse_code_from_string(input_string: str) -> list[str]:
    """
    从输入字符串中提取代码片段和命令:
    - 仅在代码块（```...```）外按分号分割语句
    - 提取代码块内的内容
    - 识别特殊命令 WAIT, DONE, FAIL

    返回一个字符串列表，每个元素是一段代码或命令。"""
    trimmed = input_string.strip()
    if trimmed in ('WAIT', 'DONE', 'FAIL'):
        return [trimmed]

    code_block_pattern = re.compile(r'```(?:\w+\s+)?(.*?)```', re.DOTALL)

    def split_outside_code(text: str) -> list[str]:
        parts = []
        buf = []
        in_block = False
        i = 0
        while i < len(text):
            if text.startswith('```', i):
                in_block = not in_block
                buf.append('```')
                i += 3
            elif text[i] == ';' and not in_block:
                segment = ''.join(buf).strip()
                if segment:
                    parts.append(segment)
                buf = []
                i += 1
            else:
                buf.append(text[i])
                i += 1
        last = ''.join(buf).strip()
        if last:
            parts.append(last)
        return parts

    segments = split_outside_code(input_string)
    commands = {'WAIT', 'DONE', 'FAIL'}
    results = []

    for seg in segments:
        seg = seg.strip()
        if seg in commands:
            results.append(seg)
            continue
        for match in code_block_pattern.findall(seg):
            code = match.strip()
            results.append(code)
        # if not code_block_pattern.search(seg) and seg:
        #     results.append(seg)

    return results

def save_figure(img, intermediate_results_dir):
    os.makedirs(intermediate_results_dir, exist_ok=True) 
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"{intermediate_results_dir}/intermediate_steps/{timestamp}.jpg"

    img.save(file_path)
    logger.info(f"Image saved as: {file_path}")
    with open(file_path, "rb") as file:
        image_bytes = file.read()
    return image_bytes

def print_messages(dc_messages, function_name):
    def format_message_content(message):
        content = message.get("content", '')
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content and isinstance(content[0], dict) and "text" in content[0]:
            return content[0]["text"] + " <image>"
        return "<image>"

    printable_messages = [
        {
            "role": message["role"],
            "content": format_message_content(message)
        }
        for message in dc_messages
    ]

    print(f'Messages in {function_name}: {printable_messages}')

  
class OSworld_test_Agent():
    def __init__(self, env: DesktopEnv, example_result_dir: str, cfg_args: dict, 
                 screen_width: int, screen_height: int) -> None:
        # Call the parent class's constructor
        self.platform = "ubuntu"
        self.model = cfg_args['model']
        self.max_tokens = cfg_args['max_tokens']
        self.top_p = cfg_args['top_p']
        self.temperature = cfg_args['temperature']
        self.action_space = "pyautogui"
        self.max_trajectory_length = cfg_args['max_trajectory_length']
        self.env = env
        self.intermediate_results_dir = example_result_dir
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.oss_llm = None
        self.steps = 0
        self.max_steps = cfg_args['max_steps']
        self.thoughts = []
        self.actions = []
        self.observations = []

        if self.action_space == "computer_13":
            self.system_message = ''
        elif self.action_space == "pyautogui":
            self.system_message = SYS_PROMPT_IN_SCREENSHOT_OUT_CODE_ONE_COMMAND
        else:
            raise ValueError("Invalid action space: " + self.action_space)
        self.oss_llm_init()
        
    def reset(self, _logger=None):
        '''
        Clean everything
        '''
        global logger
        logger = _logger if _logger is not None else logging.getLogger("desktopenv.agent")

        self.thoughts = []
        self.actions = []
        self.observations = []
    
    def update_result_dir(self, example_result_dir):
        self.intermediate_results_dir = example_result_dir
    
    def oss_llm_init(self):
        if self.oss_llm is None:
            logger.info(f"Loading model ByteDance-Seed/UI-TARS-1.5-7B into GPU...")
            self.oss_llm = LLM(
                model='ByteDance-Seed/UI-TARS-1.5-7B',
                tokenizer='ByteDance-Seed/UI-TARS-1.5-7B',
                tensor_parallel_size=2,
                gpu_memory_utilization=0.9,
                enforce_eager=True,
                max_model_len=9632,
                disable_custom_all_reduce=True,
                enable_prefix_caching=False,
                trust_remote_code=True,
            )
            logger.info(f"Model ByteDance-Seed/UI-TARS-1.5-7B loaded into GPU memory") 
    
    def call_llm(self, payload):
        if self.model.startswith("gpt"):
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"
            }
            logger.info("Generating content with GPT model: %s", self.model)
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )

            if response.status_code != 200:
                if response.json()['error']['code'] == "context_length_exceeded":
                    logger.error("Context length exceeded. Retrying with a smaller context.")
                    payload["messages"] = [payload["messages"][0]] + payload["messages"][-1:]
                    retry_response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    if retry_response.status_code != 200:
                        logger.error(
                            "Failed to call LLM even after attempt on shortening the history: " + retry_response.text)
                        return ""

                logger.error("Failed to call LLM: " + response.text)
                time.sleep(5)
                return ""
            else:
                return response.json()['choices'][0]['message']['content']
            
        elif self.model.startswith("claude"):
            client = anthropic.Anthropic()
            max_retries = 3
            messages = payload["messages"].copy()  # Make a copy to preserve original
            
            while messages and max_retries > 0:
                try:
                    completion = client.messages.create(
                        model="claude-3-7-sonnet-20250219",
                        messages=messages,
                        max_tokens=payload["max_tokens"]
                    )
                    return completion.content[0].text
                except Exception as e:
                    if "request_too_large" in str(e):
                        # Remove the second message (index 1) if it exists
                        if len(messages) > 1:
                            messages.pop(1)
                            continue
                    
                    max_retries -= 1
                    if max_retries > 0:
                        time.sleep(5)
                    else:
                        logger.error("All attempts to call Claude failed.")
                        return ""

    def predict(self, instruction: str, obs: dict):
        '''
        Predict the next action(s) based on the current observation.
        Input two things: instruction (Task description), obs:
        self.observations.append({
                "screenshot": base64_image,
                "accessibility_tree": None
            })
        return two things: response, actions
        '''
        """
        Predict the next action(s) based on the current observation.
        """
        self.steps += 1
        logger.info("Current step: %s", self.steps)
        if self.steps > self.max_steps-1:
            self.steps = 0
            response = '```FAIL```'
            logger.info("RESPONSE: %s", response)

            try:
                actions = self.parse_actions(response)
                logger.info("Actions after parse_actions: %s", actions)
                actions = self.localizaiton(actions)
                actions = clean_actions(actions)
                logger.info("Actions after localizaiton: %s", actions)
                if actions:
                    self.actions.append(actions)
                    self.thoughts.append(response)
            except ValueError as e:
                print("Failed to parse action from response", e)
                actions = None
                self.thoughts.append("")
            return response, actions   
        
        # Use the following system message for the libreoffice_calc task
        # system_message = self.system_message + "\nYou are asked to complete the following task: {}. Please input several commands at one code block for `pyautogui.typewrite()` and `pyautogui.press('enter')` operations to improve efficiency.".format(instruction)
        system_message = self.system_message + "\nYou are asked to complete the following task: {}".format(instruction)
        
        # Prepare the payload for the API call
        messages = []
        
        messages.append({
            "role": "user",
            "content":  system_message
        })

        # Append trajectory
        assert len(self.observations) == len(self.actions) and len(self.actions) == len(self.thoughts) \
            , "The number of observations and actions should be the same."

        # Cut the long message based on max_trajectory_length
        if len(self.observations) > self.max_trajectory_length:
            if self.max_trajectory_length == 0:
                _observations = []
                _actions = []
                _thoughts = []
            else:
                _observations = self.observations[-self.max_trajectory_length:]
                _actions = self.actions[-self.max_trajectory_length:]
                _thoughts = self.thoughts[-self.max_trajectory_length:]
        else:
            _observations = self.observations
            _actions = self.actions
            _thoughts = self.thoughts

        for previous_obs, previous_action, previous_thought in zip(_observations, _actions, _thoughts):

            _screenshot = previous_obs["screenshot"]

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type":"image/png",
                            "data": _screenshot,
                        }
                    },
                    {
                        "type": "text",
                        "text": "Given the screenshot as below. What's the next step that you will do to help with the task?\n" + NOTES
                    }
                ]
            })

            messages.append({
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": previous_thought.strip() if len(previous_thought) > 0 else "No valid action"
                    },
                ]
            })
            
        # Save the image
        img_save = Image.open(io.BytesIO(obs["screenshot"])).convert("RGB")
        save_image_and_convert_to_byte(img_save)
        base64_image = encode_image(obs["screenshot"])

        self.observations.append({
            "screenshot": base64_image,
            "accessibility_tree": None
        })

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Given the screenshot as below. What's the next step that you will do to help with the task?\n" + NOTES
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type":"image/png",
                        "data": base64_image,
                    }
                }
            ]
        })


        # with open("messages.json", "w") as f:
        #     f.write(json.dumps(messages, indent=4))

        # logger.info("PROMPT: %s", messages)

        try:
            # print_messages(messages, "predict")
            response = self.call_llm({
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "temperature": self.temperature
            })
        except Exception as e:
            logger.error("Failed to call" + self.model + ", Error: " + str(e))
            response = ""

        logger.info("RESPONSE: %s", response)

        try:
            actions = self.parse_actions(response)
            logger.info("Actions after parse_actions: %s", actions)
            actions = self.localizaiton(actions)
            logger.info("Actions after localizaiton: %s", actions)
            if actions:
                self.actions.append(actions)
                self.thoughts.append(response)
        except ValueError as e:
            print("Failed to parse action from response", e)
            actions = None
            self.thoughts.append("")

        return response, actions       
    
    def parse_actions(self, response: str, masks=None):
        actions = parse_code_from_string(response)
        return actions

    def localizaiton(self, actions: list):
        keywords = [
            "pyautogui.click",
            "pyautogui.dragTo",
            "pyautogui.mouseDown",
            "pyautogui.moveTo",
            "pyautogui.drag",
            "pyautogui.rightClick",
            "pyautogui.tripleClick",
            "pyautogui.doubleClick",
            "pyautogui.mouseUp",
        ]
        # Take a screenshot once for all matching actions
        byte_image = self.env.controller.get_screenshot()
        img = Image.open(io.BytesIO(byte_image))

        for idx, action in enumerate(actions):
            if any(kw in action for kw in keywords):
                icon, desc = extract_icon_and_desc(action)
                logger.info(f"Icon: {icon}, Desc: {desc}")
                if icon is None or desc is None:
                    # Skip if no valid description
                    continue

                # Locate on the screenshot
                coordination = self.image_description_to_coordinate(icon, desc, img)
                logger.info(f"Coordination for action {idx}: {coordination}")

                # Replace only if coordination is valid
                if isinstance(coordination, tuple) and len(coordination) == 2:
                    x, y = coordination
                    try:
                        new_action = replace_icon_desc_with_coordinates(action, x, y)
                        actions[idx] = new_action
                        logger.info(f"Action {idx} updated: {new_action}")
                    except (SyntaxError, ValueError) as e:
                        logger.error(f"Failed to replace coords in action {idx}: {e}")
                else:
                    logger.error(f"Coordination is not a valid tuple for action {idx}.")

        return actions
    
    def oss_llm_completion(self, messages, stop=None):
        if self.oss_llm is None:
            self.oss_llm_init()
        sampling_params = SamplingParams(
                    n=1,
                    max_tokens=9632,
                    temperature=0,
                    top_p=1.0,
                    frequency_penalty=0,
                    presence_penalty=0
                )  
        sampling_params.stop = stop
        request_output = self.oss_llm.chat(messages, sampling_params)
        # logger.debug(f"Request output: {request_output}")
        response_list = []
        for response in request_output[0].outputs:
            response_list.append(response.text)
        return response_list
        
    def _ask_llm_for_coordinate(self, image_bytes: bytes, description: str) -> tuple[int,int]:
        """向 oss_llm_completion 发送一次请求，解析并返回 (x,y)。"""
        b64 = encode_image(image_bytes)
        text = (
            "Please provide the ONE point coordinates (x, y) "
            f"of the element described as: {description}"
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": text},
                ]
            }
        ]
        result = self.oss_llm_completion(messages)
        coord = extract_coordinates(result)
        return coord       
        
    def image_description_to_coordinate(self, icon, desc, image):
        """
        Convert the image description to coordinate for accurate mouse click.
        """
        # Crop the image
        global CURRENT_WHOLE_IMAGE
        CURRENT_WHOLE_IMAGE = image
        byte_image = save_image_and_convert_to_byte(image) 
        coordination = self._ask_llm_for_coordinate(byte_image, icon+" ("+desc+")")
        
        # localization
        if not coordination[0] == -1:
            byte_cropped, offset = highlight_and_save_region(coordination, half_size_x = 700, half_size_y = 250)
            coordination = self._ask_llm_for_coordinate(byte_cropped, icon+" ("+desc+")")
            dx = offset[0]
            dy = offset[1]
            coordination = (coordination[0] + dx, coordination[1] + dy)
                      
        # save the image with the red dot
        copy_img, _, _, _ = localization_point(coordination[0], coordination[1])
        if copy_img:
            save_image_and_convert_to_byte(copy_img)
        return coordination

def configs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end evaluation on the benchmark"
    )

    # environment config
    parser.add_argument("--path_to_vm", type=str, default=None)
    parser.add_argument(
        "--headless", action="store_true", help="Run in headless machine"
    )
    parser.add_argument(
        "--action_space", type=str, default="pyautogui", help="Action type"
    )
    parser.add_argument(
        "--observation_type",
        choices=["screenshot", "a11y_tree", "screenshot_a11y_tree", "som"],
        default="a11y_tree",
        help="Observation type",
    )
    parser.add_argument("--screen_width", type=int, default=1920)
    parser.add_argument("--screen_height", type=int, default=1080)
    parser.add_argument("--sleep_after_execution", type=float, default=0.5)
    parser.add_argument("--max_steps", type=int, default=50)

    # agent config
    parser.add_argument("--max_trajectory_length", type=int, default=20)
    parser.add_argument(
        "--test_config_base_dir", type=str, default="evaluation_examples"
    )

    # lm config
    parser.add_argument("--model", type=str, default="claude-3-7-sonnet-20250219")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--max_tokens", type=int, default=1500)
    parser.add_argument("--stop_token", type=str, default=None)

    # example config
    parser.add_argument("--domain", type=str, default="all")
    # parser.add_argument(
    #     "--test_all_meta_path", type=str, default="evaluation_examples/test_all.json"
    # )
    parser.add_argument(
        "--test_all_meta_path", type=str, default="evaluation_examples/test_all.json"
    )
    # logging related
    parser.add_argument("--result_dir", type=str, default="./results")
    args = parser.parse_args()

    return args

def test(args: argparse.Namespace, test_all_meta: dict) -> None:
    scores = []
    max_steps = args.max_steps

    # log args
    logger.info("Args: %s", args)
    # set wandb project
    cfg_args = {
        "path_to_vm": args.path_to_vm,
        "headless": args.headless,
        "action_space": args.action_space,
        "observation_type": args.observation_type,
        "screen_width": args.screen_width,
        "screen_height": args.screen_height,
        "sleep_after_execution": args.sleep_after_execution,
        "max_steps": args.max_steps,
        "max_trajectory_length": args.max_trajectory_length,
        "model": args.model,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "stop_token": args.stop_token,
        "result_dir": args.result_dir,
    }

    env = DesktopEnv(
        path_to_vm=args.path_to_vm,
        action_space=args.action_space,
        screen_size=(args.screen_width, args.screen_height),
        headless=args.headless,
        os_type = "Ubuntu",
        require_a11y_tree=args.observation_type
        in ["a11y_tree", "screenshot_a11y_tree", "som"],
    )

    byte_image = env.controller.get_screenshot()
    img = Image.open(io.BytesIO(byte_image))
    screen_width, screen_height = img.size

    agent = OSworld_test_Agent(env, "placeholder", cfg_args, screen_width, screen_height)

    for domain in tqdm(test_all_meta, desc="Domain"):
        for example_id in tqdm(test_all_meta[domain], desc="Example", leave=False):
            agent.steps = 0
            config_file = os.path.join(
                args.test_config_base_dir, f"examples/{domain}/{example_id}.json"
            )
            with open(config_file, "r", encoding="utf-8") as f:
                example = json.load(f)
            # run.config.update(cfg_args)

            example_result_dir = os.path.join(
                args.result_dir,
                args.action_space,
                args.observation_type,
                args.model,
                domain,
                example_id,
            )
            os.makedirs(example_result_dir, exist_ok=True)
            agent.update_result_dir(example_result_dir)
            
            # logger.info(f"[Domain]: {domain}")
            # logger.info(f"[Example ID]: {example_id}")

            instruction = example["instruction"]

            # logger.info(f"[Instruction]: {instruction}")
            # wandb each example config settings
            cfg_args["instruction"] = instruction
            cfg_args["start_time"] = datetime.datetime.now().strftime(
                "%Y:%m:%d-%H:%M:%S"
            )
            
            # example start running
            try:
                lib_run_single.run_single_example(
                    agent,
                    env,
                    example,
                    max_steps,
                    instruction,
                    args,
                    example_result_dir,
                    scores,
                )
            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"Exception in {domain}/{example_id}: {e}\nTraceback:\n{error_trace}")
                env.controller.end_recording(
                    os.path.join(example_result_dir, "recording.mp4")
                )
                with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                    f.write(
                        json.dumps(
                            {"Error": f"Time limit exceeded in {domain}/{example_id}"}
                        )
                    )
                    f.write("\n")
        # break
    env.close()
    logger.info(f"Average score: {sum(scores) / len(scores)}")

def get_unfinished(
    action_space, use_model, observation_type, result_dir, total_file_json
):
    target_dir = os.path.join(result_dir, action_space, observation_type, use_model)

    if not os.path.exists(target_dir):
        return total_file_json

    finished = {}
    for domain in os.listdir(target_dir):
        finished[domain] = []
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                if example_id == "onboard":
                    continue
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" not in os.listdir(example_path):
                        # empty all files under example_id
                        for file in os.listdir(example_path):
                            file_path = os.path.join(example_path, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path) 
                    else:
                        finished[domain].append(example_id)

    if not finished:
        return total_file_json

    for domain, examples in finished.items():
        if domain in total_file_json:
            total_file_json[domain] = [
                x for x in total_file_json[domain] if x not in examples
            ]

    return total_file_json

def get_result(action_space, use_model, observation_type, result_dir, total_file_json):
    target_dir = os.path.join(result_dir, action_space, observation_type, use_model)
    if not os.path.exists(target_dir):
        print("New experiment, no result yet.")
        return None

    all_result = []

    for domain in os.listdir(target_dir):
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" in os.listdir(example_path):
                        # empty all files under example_id
                        try:
                            all_result.append(
                                float(
                                    open(
                                        os.path.join(example_path, "result.txt"), "r"
                                    ).read()
                                )
                            )
                        except:
                            all_result.append(0.0)

    if not all_result:
        print("New experiment, no result yet.")
        return None
    else:
        print("Current Success Rate:", sum(all_result) / len(all_result) * 100, "%")
        return all_result

if __name__ == "__main__":
    ####### The complete version of the list of examples #######
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    args = configs()

    with open(args.test_all_meta_path, "r", encoding="utf-8") as f:
        test_all_meta = json.load(f)

    if args.domain != "all":
        test_all_meta = {args.domain: test_all_meta[args.domain]}

    test_file_list = get_unfinished(
        args.action_space,
        args.model,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )
    left_info = ""
    for domain in test_file_list:
        left_info += f"{domain}: {len(test_file_list[domain])}\n"
    logger.info(f"Left tasks:\n{left_info}")

    get_result(
        args.action_space,
        args.model,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )
    test(args, test_file_list)
