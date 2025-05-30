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
from typing import TYPE_CHECKING, Tuple
if TYPE_CHECKING:
    from infant.agent.agent import Agent
from PIL import Image, ImageDraw, ImageEnhance
import infant.util.constant as constant
from infant.util.debug import print_messages # for debugging
from infant.agent.memory.memory import Memory, IPythonRun
from infant.util.logger import infant_logger as logger
from infant.util.backup_image import backup_image

CURRENT_WHOLE_IMAGE = None
CURRENT_IMAGE_RANGE = None
CURRENT_RED_POINT = None

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

Assistant:
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
    Enhance the clarity of the image by resizing and sharpening it.
    """
    if scale_factor != 1:
        new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
        image = image.resize(new_size, resample=Image.LANCZOS)
    
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
    backup_image(filename)
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

def highlight_and_save_region(center: tuple[int, int], half_size_x: int = 700, half_size_y: int = 450):
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
    byte_cropped = save_image_and_convert_to_byte(constant.MOUNT_PATH, cropped)
    offset = (left, top)
    return byte_cropped, offset

def _ask_llm_for_coordinate(agent: Agent, image_bytes: bytes, description: str) -> tuple[int,int]:
    """Send a request to oss_llm_completion, parse and return (x,y)."""
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
    result = agent.vg_llm.completion(messages)
    coord = extract_coordinates(result)
    return coord

def image_description_to_coordinate(agent: Agent, icon, desc, image):
    """
    Convert the image description to coordinate for accurate mouse click.
    """
    # Crop the image
    global CURRENT_WHOLE_IMAGE
    CURRENT_WHOLE_IMAGE = image
    byte_image = save_image_and_convert_to_byte(constant.MOUNT_PATH, image)
    coordination = _ask_llm_for_coordinate(agent, byte_image, icon+" ("+desc+")")
    
    # localization
    if not coordination[0] == -1:
        byte_cropped, offset = highlight_and_save_region(coordination, half_size_x = 700, half_size_y = 450)
        coordination = _ask_llm_for_coordinate(agent, byte_cropped, icon+" ("+desc+")")
        dx = offset[0]
        dy = offset[1]
        coordination = (coordination[0] + dx, coordination[1] + dy)
                    
    # save the image with the red dot
    copy_img, _, _, _ = localization_point(coordination[0], coordination[1])
    if copy_img:
        save_image_and_convert_to_byte(constant.MOUNT_PATH, copy_img)
    return coordination


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
            image_path = extract_image_path_from_output(image_path_output, mount_path=constant.MOUNT_PATH)
            if not image_path:
                logger.error("Failed to take screenshot.")
                logger.info(f"=========End localization=========")
                return memory
            
            # Add grid to the image
            img = Image.open(image_path)
            
            # Find the coordination
            coordination = image_description_to_coordinate(agent, icon, desc, img)
            logger.info(f"Coordination: {coordination}")
            
            try:
                if isinstance(coordination, tuple) and len(coordination) == 2:
                    x, y = coordination
                    
                    # Execute the click action
                    tmp_code = memory.code
                    memory.code = replace_icon_desc_with_coordinates(memory.code, x, y) # replace the image description with the coordinate
                    method = getattr(agent.computer, memory.action)
                    memory.result = await method(memory)
                    memory.code = tmp_code
                    logger.info(f"Mouse clicked at coordinates: ({x}, {y})")
                    logger.info(f"=========End localization=========")
                    return memory
                else:
                    logger.error("Coordination is not a valid tuple.")
            except (SyntaxError, ValueError) as e:
                logger.error(f"Failed to parse coordination: {coordination}. Error: {e}")  
    return memory
