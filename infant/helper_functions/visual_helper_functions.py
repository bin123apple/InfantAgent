'''
The visual helper functions are used to help the computer to 
localize the image description to the coordinate for accurate mouse click.
The LVM localization ability is not that good.
'''
from __future__ import annotations

import os
import re
import ast
import base64
import datetime
from math import sqrt
from io import BytesIO
from typing import TYPE_CHECKING, Tuple
if TYPE_CHECKING:
    from infant.agent.agent import Agent
from infant.computer.computer import Computer
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from infant.config import config
from infant.util.debug import print_messages
from infant.agent.memory.memory import Memory, IPythonRun
from infant.util.logger import infant_logger as logger
from infant.llm.llm_api_base import LLM_API_BASED

CURRENT_WHOLE_IMAGE = None
CURRENT_IMAGE_RANGE = None
CURRENT_RED_POINT = None

# LOCALIZATION_INITIAL_PROMPT_VISUAL = '''I'm trying to perform a mouse click action, and I need your help to determine the exact coordinates of the content I need to click on.
# I will provide you with a screenshot of the screen. The coordinates are labeled along the edges of the screen.
# Here are some functions that you might find useful:
# 1. If you need to zoom in on the screen for more precise coordinate identification, please use the following function:
# localization_area(top_left: tuple | None = None, bottom_right: tuple | None = None)
# This function is used to zoom in on the screen by specifying the top-left corner and the bottom_right of the zoomed-in area.
# Args:
#     top_left (tuple | None):
#         The top-left corner of the screenshot region as a tuple of (x, y) coordinates.
#         If None, the screenshot will cover the entire screen. Defaults to None.
#     bottom_right (tuple | None):
#         The bottom-right corner of the screenshot region as a tuple of (x, y) coordinates.
#         If None, the screenshot will cover the entire screen. Defaults to None.
# 2. To check the exact screen position of a coordinate, you can use the following command:
# localization_point(x: int, y: int)
# I will draw a red dot on the screen at the specified coordinates.
# Args:
#     x (int): The x-coordinate of the point to check.
#     y (int): The y-coordinate of the point to check.
# 3. If you think the coordinates are correct, you can use the following command to finish the localization:
# localization_done(x: int, y: int)
# Args:
#     x (int): The x-coordinate of the final point.
#     y (int): The y-coordinate of the final point.
# You should place the function you would like to execute within the <localize>...</localize> tags.
# Here is an example:
# User:
# I want to click on vscode icon with the mouse. Please help me determine its **EXACT** coordinates.

# Asistant:
# let's zoom in on the screen for more precise coordinate identification.
# <localize>
# localization_area(top_left = (0, 200), bottom_right = (200, 400))
# </localize>

# User:
# The current screen's x-axis range is 0 to 200, and the y-axis range is 200 to 400.
# [Screenshot Figure]

# Asistant:
# let's check another area of the screen.
# <localize>
# localization_area(top_left = (400, 700), bottom_right = (500, 800))
# </localize>

# User:
# The current screen's x-axis range is 400 to 500, and the y-axis range is 700 to 800.
# [Screenshot Figure]

# Asistant:
# Let's check the specific location of coordinates (430, 710).
# <localize>
# localization_point(430,710)
# </localize>

# User:
# The current screen's x-axis range is 400 to 500, and the y-axis range is 700 to 800.
# The red dot is located at (430, 710).
# [Screenshot Figure]

# Assistant:
# Let's check another specific location at coordinates (450, 750).
# <localize>
# localization_point(450, 750)
# </localize>

# User:
# The current screen's x-axis range is 400 to 500, and the y-axis range is 700 to 800.
# The red dot is located at (450, 750).
# [Screenshot Figure]

# Assistant:
# We have found the coordinates of the vscode icon.
# <localize>
# localization_done(450, 750)
# </localize>

# Now, let's work on the real task:
# I want to click on {item_to_click} ({Location}) with the mouse. 
# The current screen's x-axis range is {x_range[0]} to {x_range[1]} and the y-axis range is {y_range[0]} to {y_range[1]}.
# Please help me determine its **EXACT** coordinates.
# '''.strip()

LOCALIZATION_INITIAL_PROMPT_VISUAL = '''I'm trying to perform a mouse click action, and I need your help to determine the exact coordinates of the content I need to click on.
I will provide you with a screenshot of the screen. The coordinates are labeled along the edges of the screen.
Here are some functions that you might find useful:
1. To check the exact screen position of a coordinate, you can use the following command:
localization_point(x: int, y: int)
I will draw a red dot on the screen at the specified coordinates.
Args:
    x (int): The x-coordinate of the point to check.
    y (int): The y-coordinate of the point to check.
2. If you need to move the red dot, you can use the following command:
move(dx: int, dy: int)
Args:
    dx (int): The distance to move along the x-axis. Positive values move right, negative left.
    dy (int): The distance to move along the y-axis. Positive values move down, negative up.
3. If you think the coordinates are correct, you can use the following command to finish the localization:
localization_done(x: int, y: int)
Args:
    x (int): The x-coordinate of the final point.
    y (int): The y-coordinate of the final point.
You should place the function you would like to execute within the <localize>...</localize> tags.
Here is an example:
User:
I want to click on vscode icon with the mouse. Please help me determine its **EXACT** coordinates.

Asistant:
Let's check the specific location of coordinates (430, 710).
<localize>
localization_point(430,710)
</localize>

User:
The red dot is located at (430, 710).
[Screenshot Figure]

Assistant:
Let's move the red dot to coordinates to the right by 20 pixels and down by 40 pixels.
<localize>
move(20, 40)
</localize>

User:
The current screen's x-axis range is 0 to 1920, and the y-axis range is 0 to 1080.
The red dot is located at (450, 750).
[Screenshot Figure]

Assistant:
We have found the coordinates of the vscode icon.
<localize>
localization_done(450, 750)
</localize>

Now, let's work on the real task:
I want to click on {item_to_click} ({Location}) with the mouse. 
The current screen's x-axis range is {x_range[0]} to {x_range[1]} and the y-axis range is {y_range[0]} to {y_range[1]}.
Please help me determine its **EXACT** coordinates.
'''.strip()

def localization_area(top_left: tuple | None = None,
                      bottom_right: tuple | None = None) -> Tuple[Image.Image, tuple, tuple]:
    """
    This function is used to zoom in on the screen by specifying the top-left corner and the bottom-right 
    corner of the zoomed-in area.
    
    Args:
        top_left (tuple | None):
            The top-left corner of the screenshot region as a tuple of (x, y) coordinates.
            If None, the screenshot will cover the entire screen. Defaults to None.
        bottom_right (tuple | None):
            The bottom-right corner of the screenshot region as a tuple of (x, y) coordinates.
            If None, the screenshot will cover the entire screen. Defaults to None.
            
    Returns:
        The enhanced image (after cropping and clarity enhancement).
    
    Raises:
        ValueError: If both top_left and bottom_right are provided and bottom_right is not to the bottom-right of top_left.
    """
    # Capture the entire screen
    global CURRENT_WHOLE_IMAGE
    global CURRENT_IMAGE_RANGE
    
    if top_left is None:
        top_left = (0, 0)
    if bottom_right is None:
        bottom_right = (CURRENT_WHOLE_IMAGE.width, CURRENT_WHOLE_IMAGE.height)
    
    # Validate the coordinates
    if bottom_right[0] <= top_left[0] or bottom_right[1] <= top_left[1]:
        print("Invalid coordinates: bottom_right must be to the bottom-right of top_left.")
        return None, None, None
    
    # Crop the screenshot to the specified region
    copy_img = CURRENT_WHOLE_IMAGE.copy()
    cropped_img = copy_img.crop((top_left[0], top_left[1], bottom_right[0], bottom_right[1]))
    # Enhance the image clarity using the provided function
    scale_factor = (CURRENT_WHOLE_IMAGE.width // (bottom_right[0] - top_left[0])) * (CURRENT_WHOLE_IMAGE.height // (bottom_right[1] - top_left[1]))
    # enhanced_image = enhance_image_clarity(screenshot, scale_factor=scale_factor)
    enhanced_image = enhance_image_clarity(cropped_img, scale_factor=2) # zoom twice for now
    x_range = (top_left[0], bottom_right[0])
    y_range = (top_left[1], bottom_right[1])
    CURRENT_IMAGE_RANGE = (x_range, y_range)
    return enhanced_image, x_range, y_range

def move(dx: int, dy: int) -> Tuple[Image.Image, tuple, tuple, tuple]:
    """
    Moves the current red dot by (dx, dy) relative to its current position.
    
    Args:
        dx (int): The distance to move along the x-axis. Positive values move right, negative left.
        dy (int): The distance to move along the y-axis. Positive values move down, negative up.
        
    Returns:
        A tuple containing:
          - The updated image with the red dot at the new location.
          - The x_range as a tuple (0, image_width).
          - The y_range as a tuple (0, image_height).
          - The new (x, y) position of the red dot.
        If the movement would place the red dot outside the image boundaries or if no current red dot is set,
        prints an error message and returns (None, None, None, None).
    """
    global CURRENT_WHOLE_IMAGE, CURRENT_RED_POINT

    if 'CURRENT_RED_POINT' not in globals() or CURRENT_RED_POINT is None:
        print("No current red dot set. Please set a red dot using localization_point first.")
        return None, None, None, None

    current_x, current_y = CURRENT_RED_POINT
    new_x = current_x + dx
    new_y = current_y + dy

    if new_x < 0 or new_x >= CURRENT_WHOLE_IMAGE.width or new_y < 0 or new_y >= CURRENT_WHOLE_IMAGE.height:
        return None, None, None, "Movement leads to invalid coordinates: new position is out of image dimensions."

    x_range = [0, CURRENT_WHOLE_IMAGE.width]
    y_range = [0, CURRENT_WHOLE_IMAGE.height]
    
    copy_img = CURRENT_WHOLE_IMAGE.copy()
    draw = ImageDraw.Draw(copy_img)
    
    dot_radius = 10
    dot_color = (255, 0, 0)
    
    draw.ellipse((new_x - dot_radius, new_y - dot_radius, new_x + dot_radius, new_y + dot_radius), fill=dot_color)

    CURRENT_RED_POINT = (new_x, new_y)
    
    return copy_img, x_range, y_range, (new_x, new_y)

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
        return None, None, None, "Invalid coordinates: x and y must be within the image dimensions."
    
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

def localization_done(x: int, y: int) -> tuple:
    """
    This function is used to finish the localization process by specifying the final coordinates.
    
    Args:
        x (int): The x-coordinate of the final point.
        y (int): The y-coordinate of the final point.
        
    Returns:
        None
    """
    global CURRENT_WHOLE_IMAGE
    if x < 0 or x >= CURRENT_WHOLE_IMAGE.width or y < 0 or y >= CURRENT_WHOLE_IMAGE.height:
        print("Invalid coordinates: x and y must be within the image dimensions.")
        return (0, 0)
    return (x, y)

def dispatch(func_name, args, kwargs):
    """
    根据函数名和参数自动调用对应函数。
    要求对应函数在当前作用域中可访问（例如 globals()）。
    """
    func = globals().get(func_name)
    if func is None:
        raise NameError(f"Function '{func_name}' is not defined.")

    return func(*args, **kwargs)

def enhance_image_clarity(image, scale_factor=1, 
                          sharpness_factor=2.0) -> Image.Image: 
    """
    增强图像清晰度的函数。该函数可以通过放大图像以及应用锐化滤镜来提高图像的清晰度。
    
    参数：
        image (PIL.Image): 待处理的图像。
        scale_factor (float): 放大倍率，默认为 1（不放大）。如果大于 1，则图像会相应放大。
        sharpness_factor (float): 锐化因子，默认为 2.0。1.0 表示原始图像，小于 1 会使图像更模糊，
                                  大于 1 则会增强图像的锐度。
    
    返回：
        PIL.Image: 经过增强后的图像。
    """
    # 如果需要放大图像，则按指定倍率调整尺寸
    if scale_factor != 1:
        new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
        image = image.resize(new_size, resample=Image.LANCZOS)
    
    # 使用 ImageEnhance 对图像进行锐化
    enhancer = ImageEnhance.Sharpness(image)
    enhanced_image = enhancer.enhance(sharpness_factor)
    
    return enhanced_image

def extract_image_path_from_output(output: str, mount_path: str) -> str:
    '''
    Extract the image path from the output.
    Args:
        output (str): The output string.
    Returns:
        str: The image path.
    '''
    if '<Screenshot saved at>' in output:
        screenshot_path = output.split('<Screenshot saved at>')[-1].strip()
        # mount_path = config.workspace_mount_path
        if screenshot_path.startswith("/workspace"):
            image_path = screenshot_path.replace("/workspace", mount_path, 1)
            return image_path
    return None

def parse_action(text: str) -> list:
    """
    Parse the given text to extract the actions.
    Args:
        text (str): The text to be parsed.
    Returns:
        list: The list of actions.
    """
    if not '</localize>' in text:
        text = text + '</localize>'
    pattern = r"<localize>(.*?)</localize>"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[0]

def parse_command(command_str):
    try:
        expr = ast.parse(command_str, mode='eval').body
        if not isinstance(expr, ast.Call):
            raise ValueError("Not a function call")

        func_name = expr.func.id
        args = [ast.literal_eval(arg) for arg in expr.args]
        kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in expr.keywords}
        return func_name, args, kwargs

    except Exception as e:
        raise ValueError(f"Failed to parse command: {command_str}") from e

def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8') 


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

import re

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


def crop_screenshot(image_path, command):
    """
    Extract `top_left` and `length` values from the command string,
    then crop the image based on these values.

    Args:
        image_path (str): image path
        command (str): Command string containing top_left and length.

    Returns:
        PIL.Image.Image: Cropped image.
    """
    # Define the regular expression pattern to extract `top_left` and `length`.
    pattern = r"top_left\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*length\s*=\s*(\d+)"
    match = re.search(pattern, command)

    if not match:
        logger.error("Invalid command format. Expected format: 'localization(top_left=(x,y), length=z)'")
        return None, None, None, None

    # Extract values
    top_left_x, top_left_y, length = map(int, match.groups())

    # Calculate width and height based on the 8:5 aspect ratio
    width = length
    height = int(length * 9 / 16)

    # Open the image from byte data
    img = Image.open(image_path)

    # Crop the image using the calculated dimensions
    cropped_img = img.crop((top_left_x, top_left_y, top_left_x + width, top_left_y + height))

    return cropped_img, top_left_x, top_left_y, length

def save_image_and_convert_to_byte(mount_path: str, img: Image.Image) -> bytes:
    '''
    Save the image with grid to intermediate folder and return the byte data of the image.
    Args:
        mount_path (str): The directory to save the intermediate results.
        img (Image): The image to be saved.
    Returns:
        bytes: The byte data of the image.
    '''
    os.makedirs(f'{mount_path}/intermediate_steps/', exist_ok=True) 
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{mount_path}/intermediate_steps/{timestamp}.png"
    img.save(filename)
    logger.info(f"Intermediate Image saved as: {filename}")
    with open(filename, "rb") as file:
        image_bytes = file.read()
    return image_bytes

def replace_icon_desc_with_coordinates(command, x, y):
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
    replacement = f"x={x}, y={y}"

    # # Replace the matched part with element index
    # modified_command = re.sub(pattern, replacement, command)
    if action == 'left_click':
        modified_command = f"mouse_left_click({replacement})"
    elif action == 'double_click':
        modified_command = f"mouse_double_click({replacement})"
    elif action == 'right_click':
        modified_command = f"mouse_right_click({replacement})"

    return modified_command

def image_to_base64(image_path: str) -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File not found: {image_path}")
    with open(image_path, "rb") as img_file:
        base64_data = base64.b64encode(img_file.read()).decode("utf-8")
        print(f"Base64 encoded data for {image_path}: {base64_data[:30]}...")  # Print first 30 chars for debugging

    image_url = f"data:image/png;base64,{base64_data}"
    return image_url

async def image_description_to_coordinate(agent: Agent, icon: str, desc: str, 
                                          image: Image.Image, x_range: tuple, y_range: tuple):
    """
    Convert the image description to coordinate for accurate mouse click.
    """
    # Initialize the localization memory block
    global CURRENT_WHOLE_IMAGE
    CURRENT_WHOLE_IMAGE = image
    computer = agent.computer
    if not agent.oss_llm is None:
        byte_image = save_image_and_convert_to_byte(computer.workspace_mount_path, image) 
        base64_image = encode_image(byte_image)
        text = (
            'Your task is to help the user identify the precise coordinates (x, y) of a specific area/element/object on the screen based on a description.\n'
            '- Your response should aim to point to the center or a representative point within the described area/element/object as accurately as possible.\n'
            '- If the description is unclear or ambiguous, infer the most relevant area or element based on its likely context or purpose.\n'
            '- Your answer should be a single string (x, y) corresponding to the point of the interest.\n'
            'Description: {description}\n'
            'Answer:'
        )
        messages = [
            {"role": "user", "content": [
                {"type": "text", 
                "text": text.format(description=f"I want to click the {icon}. {desc}")},
                {"type": "image_url", 
                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                "detail": "high"}
            ]}
        ]
        result = agent.oss_llm.completion(messages)[0] # No vote for now
        coordination = ast.literal_eval(result.strip())
        # save the image with the red dot
        copy_img, x_range, y_range, (x, y) = localization_point(coordination[0], coordination[1])
        save_image_and_convert_to_byte(computer.workspace_mount_path, copy_img)
        return coordination
    byte_image = save_image_and_convert_to_byte(computer.workspace_mount_path, image) 
    base64_image = encode_image(byte_image)
    messages = []
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": LOCALIZATION_INITIAL_PROMPT_VISUAL.format(item_to_click=icon, Location=desc,
                                                                  x_range=x_range, y_range=y_range)
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": "high"
                }
            }
        ]
    })
    
    iterations = 0
    while True:
        if iterations > 10:
            return (0, 0)
        
        try:
            response = agent.llm.completion(messages=messages, stop=['</localize>'])
            logger.info(f"Response in image_description_to_coordinate: {response}")
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": response}]
            })
        except Exception as e:
            raise RuntimeError("Failed to call LLM, Error: " + str(e))

        action = parse_action(response)
        fname, args, kwargs = parse_command(action)

        if 'localization_area' in action:
            enhanced_image, x_range, y_range = dispatch(fname, args, kwargs)
            text = (
                f"The current screen's x-axis range is {x_range[0]} to {x_range[1]},\n" 
                f"and the y-axis range is {y_range[0]} to {y_range[1]}."
            )
        elif 'localization_point' in action:
            enhanced_image, x_range, y_range, coordination = dispatch(fname, args, kwargs)
            if enhanced_image is None:
                text = coordination
            text = (
                f"The current screen's x-axis range is {x_range[0]} to {x_range[1]},\n"
                f"and the y-axis range is {y_range[0]} to {y_range[1]}.\n"
                f"The red dot is located at ({coordination[0]}, {coordination[1]})."
            )
        elif 'move' in action:
            enhanced_image, x_range, y_range, coordination = dispatch(fname, args, kwargs)
            if enhanced_image is None:
                text = coordination
            text = (
                f"The current screen's x-axis range is {x_range[0]} to {x_range[1]},\n"
                f"and the y-axis range is {y_range[0]} to {y_range[1]}.\n"
                f"The red dot is located at ({coordination[0]}, {coordination[1]})."
            )

        elif 'localization_done' in action:
            return dispatch(fname, args, kwargs)
        else:
            text = f"Invalid command: {action}. Please try again."
            enhanced_image = None

        message = [{"type": "text", "text": text}]
        if enhanced_image:
            byte_image = save_image_and_convert_to_byte(computer.workspace_mount_path, enhanced_image) 
            base64_image = encode_image(byte_image)
            message.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": "high"
                }
            })
        messages.append({"role": "user", "content": message})
        iterations += 1


async def localization_visual(agent: Agent, memory: Memory):
    '''
    Localize the image description to the coordinate for accurate mouse click.
    Args:
        computer (Computer): The computer object. For some basic operations.
        memory (Memory): The memory object. The memory object to be updated.
    Returns:
        Memory: The updated memory object.
    '''
    computer = agent.computer
    if isinstance(memory, IPythonRun) and memory.code:
        pattern = r"mouse_(?:left_click|double_click|move|right_click)\(.*?\)"
        match = re.search(pattern, memory.code)
        if match:
            logger.info(f"=========Start localization=========")
            # Take a screenshot
            icon, desc = extract_icon_and_desc(memory.code)
            if icon is None or desc is None:
                logger.info(f"=========End localization=========")
                return memory
            logger.info(f"Icon: {icon}, Desc: {desc}")
            screenshot_action = IPythonRun(code="take_screenshot()")
            image_path_output = await computer.run_ipython(screenshot_action)
            image_path = extract_image_path_from_output(image_path_output, mount_path=computer.workspace_mount_path)
            if not image_path:
                logger.error("Failed to take screenshot.")
                logger.info(f"=========End localization=========")
                return memory
            
            # Add grid to the image
            img = Image.open(image_path)
            x_range = (0, img.size[0])
            y_range = (0, img.size[1])
            
            # Find the coordination
            coordination = await image_description_to_coordinate(agent, icon, desc, 
                                                                 img, x_range, y_range)
            logger.info(f"Coordination: {coordination}")
            
            try: 
                if isinstance(coordination, tuple) and len(coordination) == 2:
                    x, y = coordination 
                    memory.code = replace_icon_desc_with_coordinates(memory.code, x, y) # replace the image description with the coordinate
                    logger.info(f"Mouse clicked at coordinates: ({x}, {y})")
                    logger.info(f"=========End localization=========")
                    return memory
                else:
                    logger.error("Coordination is not a valid tuple.")
            except (SyntaxError, ValueError) as e:
                logger.error(f"Failed to parse coordination: {coordination}. Error: {e}")  
    return memory
