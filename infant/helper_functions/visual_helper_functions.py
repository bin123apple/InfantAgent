'''
The visual helper functions are used to help the computer to 
localize the image description to the coordinate for accurate mouse click.
The LVM localization ability is not that good.
'''
from __future__ import annotations

import os
import re
import copy
import base64
import datetime
from math import sqrt
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from infant.agent.agent import Agent
from infant.computer.computer import Computer
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from infant.config import config
from infant.util.debug import print_messages
from infant.agent.memory.memory import Memory, IPythonRun
from infant.util.logger import infant_logger as logger
from infant.llm.llm_api_base import LLM_API_BASED

LOCALIZATION_CHECK_DOT_PROMPT = '''I have marked the coordinates you selected with a red dot in the image. 
I want to click on {item_to_click} ({Location}) with the mouse. 
A part of screenshot of my computer screen is provided.
It is divided into sections with dashed lines, and coordinates labeled around the edges of the screen. 
Its X-axis range is: {x_range} and its Y-axis range is: {y_range}. 
Please confirm whether the selected coordinates correctly represent the position of {item_to_click}.
If not, use the following command to move the red dot to the correct coordinates:
<localize>
move(direction: str, distance: int)
</localize>
Where:
direction: Specifies the movement direction ("up", "down", "left", "right").
distance: Specifies the movement distance (integer value).
For example, if you want to move the red dot 100 pixels upward, you can use the following command:
<localize>
move(direction = "up", distance = 100)
</localize>
Currently the dot is {left_distance} pixels from the screen's left, {right_distance} pixels from the right, {bottom_distance} pixels from the bottom, and {top_distance} pixels from the top.
If you believe the red dot you selected correctly represent the position of {item_to_click}, or the {item_to_click} is not visible in the screenshot,
please respond with <|command_correct|>.'''


LOCALIZATION_CHECK_DOT_USER_PROMPT = '''Please confirm whether the selected coordinates correctly represent the position of {item_to_click}.
If not, use the 
<localize>
move(direction: str, distance: int)
</localize>
command to move the red dot to the correct coordinates.
In each <localize>...</localize> tag, you can use only one `move(direction: str, distance: int)` command.
If you believe the red dot you selected correctly represent the position of {item_to_click}, please respond with <|command_correct|>.'''


LOCALIZATION_CHECK_RECTANGLE_PROMPT = '''I have marked the area you selected with a red rectangle in the image. 
I want to click on {item_to_click} ({Location}) with the mouse.
A part of screenshot of my computer screen is provided. 
It is divided into sections with dashed lines, and coordinates labeled around the edges of the screen. 
Its X-axis range is: {x_range} and its Y-axis range is: {y_range}.
Please confirm whether the {item_to_click} is inside the red rectangle you selected. 
If it is not, use the following command to adjust the red rectangle so that {item_to_click} is inside:
<localize>
move(direction: str, distance: int)
</localize>
Where:
direction: Specifies the movement direction ("up", "down", "left", "right").
distance: Specifies the movement distance (integer value).
For example, if you want to move the red rectangle 100 pixels upward, you can use the following command:
<localize>
move(direction = "up", distance = 100)
</localize>
Currently the rectangle's left edge is {left_distance} pixels from the screen's left, the right edge is {right_distance} pixels from the right, the bottom edge is {bottom_distance} pixels from the bottom, and the top edge is {top_distance} pixels from the top.
If you believe the {item_to_click} is inside the red rectangle you selected, or the {item_to_click} is not visible in the screenshot,
please respond with <|command_correct|>.'''


LOCALIZATION_CHECK_RECTANGLE_USER_PROMPT = '''Please confirm whether the {item_to_click} is inside the red rectangle you selected. 
If not, use the 
<localize>
move(direction: str, distance: int)
</localize>
command to adjust the red rectangle so that {item_to_click} is inside.
In each <localize>...</localize> tag, you can use only one `move(direction: str, distance: int)` command.
If you believe the {item_to_click} is inside the red rectangle you selected, please respond with <|command_correct|>.'''


NOTES = '''NOTE: If you would like to use the `pyautogui.click` command, please replace the `x` and `y` parameters with the target you want to click on and a descriptive text of its position.'''


LOCALIZATION_SYSTEM_PROMPT_VISUAL = '''I want to click on {item_to_click} with the mouse. 
Please help me determine the exact coordinates I need to click on. 
I will provide you with a screenshot of my computer screen, divided into sections with dashed lines, and coordinates labeled around the edges of the screen. 
If you need to zoom in on the screen for more precise coordinate identification, please use the following function:
localization(top_left: tuple | None = None, length: int | None = None)
This function is used to zoom in on the screen by specifying the top-left corner and the length of the zoomed-in area.
Args:
    top_left (tuple | None): 
        The top-left corner of the screenshot region as a tuple of (x, y) coordinates, where 0 <= x <= 1920 and 0 <= y <= 1080.
        If None, the screenshot will cover the entire screen. Defaults to None.
    
    length (int | None): 
        The side length of the screenshot region, forming a square, where 0 <= length <= 1920.
        If None, the screenshot region will cover the entire screen or be determined dynamically. Defaults to None.
If you believe you have found the correct coordinates, please use the command localization_done(x: int, y: int) where 0 <= x <= 1920 and 0 <= y <= 1080 to complete the localization process.
You only need to generate the function itself and place it within the <localize>...</localize> tags.
For example:
User:
I want to click on {item_to_click} with the mouse. Please help me determine its **EXACT** coordinates.

Asistant:
<localize>
localization(top_left = (200, 600), length = 400)
</localize>

User:
Screenshot Figure

Asistant:
<localize>
localization(top_left = (400, 700), length = 200)
</localize>

User:
Screenshot Figure

Asistant:
The coordinates are (530,710).:
<localize>
localization_done(530,710)
</localize>

Now, let's work on the real task:
'''

LOCALIZATION_CORRECTION_SYSTEM_PROMPT = '''
I want to click on {item_to_click} ({Location}) with the mouse.
Please help me determine whether {item_to_click} is located in the position corresponding to the red rectangle or the red dot I selected.
'''.strip()


LOCALIZATION_USER_INITIAL_PROMPT_VISUAL = '''I want to click on {item_to_click} ({Location}) with the mouse. Please help me determine its **EXACT** coordinates.
I have provided you with the current screenshot. Its X-axis range is: {x_range} and its Y-axis range is: {y_range}.
You can use localization() function to zoom in on the screen for more precise coordinate identification.'''.strip()

def enhance_image_clarity(image, scale_factor=1, sharpness_factor=2.0):
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

def extract_image_path_from_output(output: str):
    '''
    Extract the image path from the output.
    Args:
        output (str): The output string.
    Returns:
        str: The image path.
    '''
    if '<Screenshot saved at>' in output:
        screenshot_path = output.split('<Screenshot saved at>')[-1].strip()
        mount_path = config.workspace_mount_path
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

def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')

def draw_dot(screenshot, last_top_left, last_length, coordination, screen_width, screen_height):
    """
    Draws a red dot on the image at the specified coordination within a cropped screenshot.

    Args:
        screenshot (Image): 待修改的截图图像。
        last_top_left (tuple): 裁剪区域的左上角坐标 (x, y)。
        last_length (int): 裁剪区域的边长（宽度按 5/8 计算，这里保留原有逻辑，即高度按 9/16 计算）。
        coordination (tuple): 红点在裁剪区域内的 (x, y) 坐标。
        screen_width (int): 屏幕宽度（备用）。
        screen_height (int): 屏幕高度（备用）。

    Returns:
        tuple: (cropped_img_dot, distances, actual_coordination)，其中 distances 是一个字典，
            包含 'left', 'right', 'top', 'bottom' 四个方向上红点到裁剪图像边缘的距离，
            actual_coordination 为实际绘制红点的坐标。
    """
    from PIL import ImageDraw

    # 转换为整数
    last_length = int(last_length)

    # 计算裁剪区域的高度（这里原代码使用了9/16比例）
    cropped_height = int(last_length * 9 // 16)

    # 获取裁剪区域左上角坐标
    region_x, region_y = last_top_left

    # 定义裁剪区域右下角坐标
    region_right = region_x + last_length
    region_bottom = region_y + cropped_height

    dot_x, dot_y = coordination

    draw = ImageDraw.Draw(screenshot)
    # 根据裁剪区域尺寸调整红点半径
    dot_radius = max(5, int(min(last_length, cropped_height) * 0.02))
    dot_color = (255, 0, 0)

    # 如果红点不完全在裁剪区域内，则调整坐标使其贴着裁剪区域边缘
    if not (region_x <= dot_x <= region_right and region_y <= dot_y <= region_bottom):
        clamped_x = min(max(dot_x, region_x), region_right)
        clamped_y = min(max(dot_y, region_y), region_bottom)
        actual_coordination = (clamped_x, clamped_y)
    else:
        actual_coordination = (dot_x, dot_y)

    # 绘制红点
    bbox = [
        actual_coordination[0] - dot_radius, actual_coordination[1] - dot_radius,
        actual_coordination[0] + dot_radius, actual_coordination[1] + dot_radius
    ]
    draw.ellipse(bbox, fill=dot_color, outline=dot_color)

    # 裁剪图像
    cropped_img_dot = screenshot.crop((region_x, region_y, region_right, region_bottom))

    # 计算红点在裁剪图像内的相对坐标
    relative_x = actual_coordination[0] - region_x
    relative_y = actual_coordination[1] - region_y

    # 计算红点到裁剪图像四个边的距离
    distances = {
        'left': relative_x,
        'top': relative_y,
        'right': last_length - relative_x,
        'bottom': cropped_height - relative_y
    }

    return cropped_img_dot, distances, actual_coordination

def draw_rectangle(screenshot, last_top_left, last_length, new_top_left, 
                   new_length, screen_width, screen_height):
    """
    Args:
        screenshot (Image): 待修改的截图图像。
        last_top_left (tuple): 裁剪区域的左上角坐标 (x, y)。
        last_length (int): 裁剪矩形的边长（宽度按 9/16 计算）。
        new_top_left (tuple): 在裁剪区域内绘制矩形的左上角坐标 (x, y)。
        new_length (int): 绘制矩形的边长（宽度按 9/16 计算）。
        screen_width (int): 屏幕宽度（用于特殊处理）。
        screen_height (int): 屏幕高度（用于特殊处理）。

    Returns:
        tuple: (cropped_img, distances)，其中 distances 是一个字典，
            包含 'left', 'right', 'top', 'bottom' 四个方向上矩形与裁剪图像边缘的距离。
    """
    from PIL import ImageDraw

    # 转换为整数
    last_length = int(last_length)
    new_length = int(new_length)

    # 计算裁剪区域和绘制矩形的宽度（按9:16比例）
    last_width = int(last_length * 9 // 16)  # 裁剪区域的宽度
    new_width = int(new_length * 9 // 16)      # 绘制矩形的宽度

    # 根据 last_length 决定边框线宽
    if last_length >= 960:
        rect_width = 10
    elif 960 > last_length >= 240:
        rect_width = 6
    else:
        rect_width = 3

    # 裁剪区域的左上角和右下角坐标
    region_x, region_y = last_top_left
    region_right = region_x + last_length
    region_bottom = region_y + last_width

    draw = ImageDraw.Draw(screenshot)

    # 新矩形在 screenshot 上的坐标
    nx, ny = new_top_left
    new_right = nx + new_length
    new_bottom = ny + new_width

    # 初始化变量，用于记录实际绘制的矩形左上角坐标
    if (region_x <= nx <= region_x + last_length and region_y <= ny <= region_y + last_width and
            region_x <= new_right <= region_x + last_length and region_y <= new_bottom <= region_y + last_width):
        # 如果新矩形完全在裁剪区域内，则直接绘制
        rect_x, rect_y = new_top_left
        rect_bbox = [rect_x, rect_y, rect_x + new_length, rect_y + new_width]
        draw.rectangle(rect_bbox, outline=(200, 0, 0), width=rect_width)
        actual_rect_top_left = (rect_x, rect_y)
    else:
        # 如果新矩形不完全在裁剪区域内，则调整坐标使其贴着裁剪区域边缘
        clamped_x = min(max(nx, region_x), region_right - new_length)
        clamped_y = min(max(ny, region_y), region_bottom - new_width)
        rect_bbox = [clamped_x, clamped_y, clamped_x + new_length, clamped_y + new_width]
        draw.rectangle(rect_bbox, outline=(200, 0, 0), width=rect_width)
        actual_rect_top_left = (clamped_x, clamped_y)

    # 裁剪出区域图像
    cropped_img = screenshot.crop((region_x, region_y, region_right, region_bottom))

    # 计算矩形在裁剪图像内的相对位置
    drawn_x, drawn_y = actual_rect_top_left
    relative_x = drawn_x - region_x
    relative_y = drawn_y - region_y

    # 裁剪图像的尺寸
    cropped_width = last_length
    cropped_height = last_width

    # 计算矩形到裁剪图像四边的距离
    distances = {
        'left': relative_x,
        'top': relative_y,
        'right': cropped_width - (relative_x + new_length),
        'bottom': cropped_height - (relative_y + new_width)
    }

    return cropped_img, distances, actual_rect_top_left

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

def process_image_and_draw_grid(intermediate_results_dir, img, length, grid_offset=(0, 0),draw_type="rectangle"):
    '''
    Save the image with grid to intermediate folder and return the byte data of the image.
    Args:
        intermediate_results_dir (str): The directory to save the intermediate results.
        img (Image): The image to be processed.
        length (int): The length of the grid.
        grid_offset (tuple): The offset of the grid.
        draw_type (str): The type of the grid to be drawn.
    Returns:
        bytes: The byte data of the image.
    '''
    os.makedirs(f'{intermediate_results_dir}/intermediate_steps/', exist_ok=True) 
    processed_img, x_range, y_range = draw_grid(img, length=length, offset=grid_offset, draw_type=draw_type)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{intermediate_results_dir}/intermediate_steps/{timestamp}.jpg"
    processed_img.save(filename)
    logger.info(f"grid Image saved as: {filename}")
    with open(filename, "rb") as file:
        image_bytes = file.read()
    return image_bytes, x_range, y_range

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


# def draw_grid(img, length, offset=(0, 0), draw_type="rectangle"):
#     """
#     Draws a grid with fixed divisions (2 horizontal lines and 3 vertical lines),
#     and labels the intersection points based on global coordinates.
#     Now, adds a black outer frame region as a background, and places red coordinate labels
#     on the frame region instead of inside the grid.
#     """

#     draw = ImageDraw.Draw(img)
#     width, height = img.size
#     if offset:
#         offset_x, offset_y = offset
#     else:
#         offset_x, offset_y = 0, 0

#     # Fixed divisions: 3 horizontal regions and 4 vertical regions
#     num_horizontal_lines = 5
#     num_vertical_lines = 7

#     # Calculate step sizes based on the screen size
#     step_x = width // (num_vertical_lines + 1)
#     step_y = height // (num_horizontal_lines + 1)

#     # Define line color, line style, and font size
#     grid_color = (200, 0, 0)  # Deep red (RGB)
#     label_color = "red"  # Red labels
#     dash_length = 10  # Length of each dash for dashed lines
#     font_size = max(int((length / 40)), 
#                     int(sqrt((width * height) / 2560)),
#                     8)  # Adjust font size based on screen area

#     # Load font
#     try:
#         font = ImageFont.truetype("DejaVuSans.ttf", font_size)
#     except:
#         font = ImageFont.load_default()

#     # Use textbbox to calculate maximum label dimensions
#     max_x_label_width = 0
#     max_y_label_width = 0

#     for i in range(num_vertical_lines + 2):
#         label = f"{i * step_x + offset_x}"
#         bbox = draw.textbbox((0, 0), label, font=font)
#         max_x_label_width = max(max_x_label_width, bbox[2] - bbox[0])

#     for j in range(num_horizontal_lines + 2):
#         label = f"{j * step_y + offset_y}"
#         bbox = draw.textbbox((0, 0), label, font=font)
#         max_y_label_width = max(max_y_label_width, bbox[2] - bbox[0])

#     frame_thickness_x = max_x_label_width  # Match longest X-coordinate label
#     frame_thickness_y = font_size  # Match font size for Y-coordinate label height

#     # print(f"Frame thickness: {frame_thickness_x} x {frame_thickness_y}")

#     # Create a new image with the black frame
#     new_width = width + 2 * frame_thickness_x
#     new_height = height + 2 * frame_thickness_y
#     new_img = Image.new("RGB", (new_width, new_height), "black")

#     # Paste the original image onto the new background
#     new_img.paste(img, (frame_thickness_x, frame_thickness_y))
#     draw = ImageDraw.Draw(new_img)

#     if draw_type == "???": # only draw the grid for the rectangle, not for the dot
#         # Draw vertical dashed lines
#         for i in range(1, num_vertical_lines + 1):
#             x = i * step_x + frame_thickness_x
#             for y in range(frame_thickness_y, height + frame_thickness_y, dash_length * 2):
#                 draw.line([(x, y), (x, y + dash_length)], fill=grid_color, width=1)

#         # Draw horizontal dashed lines
#         for i in range(1, num_horizontal_lines + 1):
#             y = i * step_y + frame_thickness_y
#             for x in range(frame_thickness_x, width + frame_thickness_x, dash_length * 2):
#                 draw.line([(x, y), (x + dash_length, y)], fill=grid_color, width=1)

#     # Label X-coordinates on the top and bottom frame
#     for i in range(num_vertical_lines + 2):
#         x = i * step_x + frame_thickness_x
#         label = f"{i * step_x + offset_x}"
#         # Top frame
#         draw.text(
#             (x - max_x_label_width // 2, frame_thickness_y // 2 - font_size // 2), label, fill=label_color, font=font
#         )
#         # Bottom frame
#         draw.text(
#             (x - max_x_label_width // 2, height + frame_thickness_y), label, fill=label_color, font=font
#         )

#     # Label Y-coordinates on the left and right frame
#     for j in range(num_horizontal_lines + 2):
#         y = j * step_y + frame_thickness_y
#         label = f"{j * step_y + offset_y}"
#         # Left frame
#         draw.text(
#             (frame_thickness_x // 2 - max_y_label_width // 2, y - font_size // 2), label, fill=label_color, font=font
#         )
#         # Right frame
#         draw.text(
#             (width + frame_thickness_x, y - font_size // 2), label, fill=label_color, font=font
#         )
        
#     # Calculate the range of x and y coordinates
#     x_range = (offset_x, offset_x + (num_vertical_lines + 1) * step_x)
#     y_range = (offset_y, offset_y + (num_horizontal_lines + 1) * step_y)
    
#     return new_img, x_range, y_range

def draw_grid(img, length, offset=(0, 0), draw_type="rectangle"):
    """
    绘制固定分割网格（5条水平线和7条垂直线），并基于全局坐标标注交点。
    此函数首先将输入图像按比例放大（同时参考长度也同步放大），
    然后添加黑色边框区域作为背景，并在边框上标注红色坐标标签，而不是直接在网格内部标注。
    
    参数：
        img (PIL.Image): 输入图像。
        length (int): 用于调整字体大小和网格间距的参考边长。
        offset (tuple): 全局坐标偏移 (offset_x, offset_y)。
        draw_type (str): 绘制类型。若为 "rectangle"，则绘制虚线网格；其他类型可按需求扩展。
        scale_factor (float): 图像放大倍率（保持长宽比），默认为1（不放大）。
        
    返回：
        tuple: (new_img, x_range, y_range)
            new_img: 添加边框和坐标标签后的图像。
            x_range, y_range: 网格对应的全局坐标范围。
    """
    width_original, height_original = img.size 
    scale_factor= int(1920//width_original)
    # 根据 scale_factor 放大图像，并同步调整参考边长
    if scale_factor != 1:
        new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
        img = img.resize(new_size, resample=Image.LANCZOS)  

    # 开始绘制网格与标签
    draw = ImageDraw.Draw(img)
    width, height = img.size
    offset_x, offset_y = offset if offset else (0, 0)

    # 固定分割：共5条水平线和7条垂直线
    num_horizontal_lines = 5
    num_vertical_lines = 7

    # 根据图像尺寸计算步长
    step_x = length // (num_vertical_lines + 1)
    step_y = length // 16 * 9 // (num_horizontal_lines + 1)

    # 定义网格颜色、标注颜色和虚线参数
    label_color = "red"       # 红色标签
    font_size = max(int((width_original * scale_factor / 40)), int(sqrt((width * height) / 2560)), 8)

    # 尝试加载字体，否则使用默认字体
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # 计算X、Y轴上最大标签的宽度（用于边框预留）
    max_x_label_width = 0
    max_y_label_width = 0

    for i in range(num_vertical_lines + 2):
        label = f"{i * step_x + offset_x}"
        bbox = draw.textbbox((0, 0), label, font=font)
        max_x_label_width = max(max_x_label_width, bbox[2] - bbox[0])

    for j in range(num_horizontal_lines + 2):
        label = f"{j * step_y + offset_y}"
        bbox = draw.textbbox((0, 0), label, font=font)
        max_y_label_width = max(max_y_label_width, bbox[2] - bbox[0])

    # 使用标签尺寸作为边框预留空间
    frame_thickness_x = max_x_label_width
    frame_thickness_y = font_size

    # 新图像尺寸：原图加上两侧边框
    new_width = width + 2 * frame_thickness_x
    new_height = height + 2 * frame_thickness_y
    new_img = Image.new("RGB", (new_width, new_height), "black")
    new_img.paste(img, (frame_thickness_x, frame_thickness_y))
    draw = ImageDraw.Draw(new_img)

    # 在上、下边框标注X轴坐标
    for i in range(num_vertical_lines + 2):
        x = i * step_x * scale_factor + frame_thickness_x
        label = f"{i * step_x + offset_x}"
        # 上边框
        draw.text(
            (x - max_x_label_width // 2, frame_thickness_y // 2 - font_size // 2),
            label, fill=label_color, font=font
        )
        # 下边框
        draw.text(
            (x - max_x_label_width // 2, height + frame_thickness_y),
            label, fill=label_color, font=font
        )

    # 在左右边框标注Y轴坐标
    for j in range(num_horizontal_lines + 2):
        y = j * step_y * scale_factor + frame_thickness_y
        label = f"{j * step_y + offset_y}"
        # 左边框
        draw.text(
            (frame_thickness_x // 2 - max_y_label_width // 2, y - font_size // 2),
            label, fill=label_color, font=font
        )
        # 右边框
        draw.text(
            (width + frame_thickness_x, y - font_size // 2),
            label, fill=label_color, font=font
        )
        
    # 计算全局坐标范围
    x_range = (offset_x, offset_x + (num_vertical_lines + 1) * step_x)
    y_range = (offset_y, offset_y + (num_horizontal_lines + 1) * step_y)
    
    return new_img, x_range, y_range

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
            image_path = extract_image_path_from_output(image_path_output)
            if not image_path:
                logger.error("Failed to take screenshot.")
                logger.info(f"=========End localization=========")
                return memory
            
            # Add grid to the image
            img = Image.open(image_path)
            computer.screen_width = img.size[0]
            computer.screen_height = img.size[1]
            grid_image , x_range, y_range = process_image_and_draw_grid(computer.intermediate_results_dir, 
                                                        img, computer.screen_width, grid_offset=(0, 0)) 
            
            # Find the coordination
            coordination = await image_description_to_coordinate(agent, computer, icon, desc, grid_image, x_range, y_range)
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

async def image_description_to_coordinate(agent: Agent, computer: Computer, icon: str, desc: str, grid_image,
                                        x_range: int, y_range: int):
    """
    Convert the image description to coordinate for accurate mouse click.
    """
    # Initialize the localization memory block
    byte_image = encode_image(grid_image)    
    messages = []
    messages.append({'role': 'system', 'content': LOCALIZATION_SYSTEM_PROMPT_VISUAL.format(item_to_click=icon)})
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": LOCALIZATION_USER_INITIAL_PROMPT_VISUAL.format(item_to_click=icon, Location=desc, 
                                                                x_range=x_range, y_range=y_range)
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
    last_response = ''
    iterations = 0
    while True:
        if iterations > 5:
            coordination = (0, 0)
        try:
            # print_messages(messages, "image_description_to_coordinate")
            response,_ = agent.llm.completion(messages=messages, stop=['</localize>'])
            logger.info(f"Response in image_description_to_coordinate: {response}")
        except Exception as e:
            logger.error("Failed to call" + computer.model + ", Error: " + str(e))
            response = ""
        if 'localization(' in response or 'localization_done' in response:
            localization_action = await localizaiton_correction(agent, computer, response, last_response, messages, 
                                                                item_to_click=icon, Location=desc, 
                                                                x_range=x_range, y_range=y_range) 
            action = localization_action # e.g. localization(top_left=0,0),length=SCREEN_WIDTH
        else: # The answer is not a localization command
            localization_action = f'localization(top_left=(0, 0), length={computer.screen_width})' # use the full screen
            action = localization_action
        logger.info(f"Action in image_description_to_coordinate: {action}")
        if any(f'<localize>{localization_action}</localize>' in message['content'] for message in messages if 'content' in message): # for repeat commands
            messages.append({"role": "assistant","content":f'<localize>{action}</localize>'})
            messages.append({"role": "user","content":'You have used the same localization command. Please provide another correct localization command.'})
        else:
            if 'localization(' in action: # continue to zoom in 
                # draw grid for the next localization
                last_response = f'<localize>{action}</localize>'
                messages.append({"role": "assistant","content":f'<localize>{action}</localize>'})
                screenshot_action = IPythonRun(code="take_screenshot()")
                image_path_output = await computer.run_ipython(screenshot_action)
                image_path = extract_image_path_from_output(image_path_output)

                cropped_img, top_left_x, top_left_y, length = crop_screenshot(image_path, action)
                if cropped_img:
                    grid_image, x_range, y_range = process_image_and_draw_grid(computer.intermediate_results_dir,
                                                            cropped_img, length,
                                                            grid_offset=(top_left_x, top_left_y))
                else:
                    return (0, 0)
                grid_image = encode_image(grid_image) 
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f'Here is the zoomed-in image. it is X-axis range is: {x_range} and its Y-axis range is: {y_range}'
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{grid_image}",
                                "detail": "high"
                            }
                        }
                    ]
                })
                
            elif 'localization_done' in action: # finish localization
                coordination = extract_coordination(action)
                return coordination # tuple
            else:
                messages.append({"role": "assistant","content":response})
                messages.append({"role": "user","content":action})
        iterations += 1

async def localizaiton_correction(agent: Agent, computer: Computer, response: str, last_response: str, messages: list, 
                            item_to_click: str, Location: str, x_range: int, y_range: int):
    '''
    Try single turn dialogues to correct the localization command.
    Check if the zoom in/localization command is correct.
    Args:
        response (str): The response from the model.
        last_response (str): The last response from the model.
        messages (list): The list of messages.
        item_to_click (str): The item to click.
        Location (str): The location of the item.
        x_range (int): The x-axis range of the image.
        y_range (int): The y-axis range of the image.
    Returns:
        str: The corrected localization command.
    '''
    logger.info(f"last_response in localizaiton_correction: {last_response}")
    if 'localization(' in last_response:
        regex = r"top_left\s*=\s*\((\d+,\s*\d+)\)|length\s*=\s*(\d+)"
        matches = re.findall(regex, last_response)
        for match in matches:
            # print(match)
            if match[0]:  # Matches top_left
                last_top_left = tuple(map(int, match[0].split(',')))
            if match[1]:  # Matches length
                last_length = int(match[1])
    else: # Use full screen as the default value
        last_top_left = (0, 0)
        last_length = computer.screen_width
    
    localization_action = parse_action(response)
    
    # dot situation
    if 'localization_done' in localization_action: # Use dot localization system message
        draw_type = "dot"
        
        dc_messages_initial = copy.deepcopy(messages)      
        for message in dc_messages_initial:
            if 'role' in message and message['role'] == 'system':
                message['role'] = 'user'
                
        coordination = extract_coordination(localization_action)
        screenshot_action = IPythonRun(code="take_screenshot()")
        image_path_output = await computer.run_ipython(screenshot_action)
        image_path = extract_image_path_from_output(image_path_output)
        screenshot = Image.open(image_path)
        cropped_img_dot, edge_distances, actual_coordination = draw_dot(screenshot, last_top_left, last_length, coordination, 
                                    computer.screen_width, computer.screen_height)
        if cropped_img_dot:
            if isinstance(cropped_img_dot, str): # initial cropped_img_dot is a str
                return cropped_img_dot
            else: # cropped_img_dot is an image
                cropped_img_dot, x_range, y_range = process_image_and_draw_grid(computer.intermediate_results_dir, 
                                                            cropped_img_dot, last_length, 
                                                            grid_offset=last_top_left, draw_type="dot") 
                logger.info(f'x_range: {x_range}, y_range: {y_range}')
                image_url = encode_image(cropped_img_dot)
                dc_messages = dc_messages_initial + [{'role': 'user',
                    'content': [{
                                    "type": "text",
                                    "text": LOCALIZATION_CHECK_DOT_PROMPT.format(item_to_click=item_to_click, 
                                                                                Location=Location, 
                                                                                left_distance = edge_distances['left'],
                                                                                right_distance = edge_distances['right'],
                                                                                bottom_distance = edge_distances['bottom'],
                                                                                top_distance = edge_distances['top'],
                                                                                x_range=x_range, 
                                                                                y_range=y_range)
                                },
                                {"type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_url}",
                                                "detail": "high"}}]}]  
        current_action = f'localization_done({int(actual_coordination[0])},{int(actual_coordination[1])})' 
            
    # rectangle situation                  
    elif 'localization(' in localization_action: # Use rectangle localization system message
        draw_type = "rectangle"
        
        dc_messages_initial = copy.deepcopy(messages)      
        for message in dc_messages_initial:
            if 'role' in message and message['role'] == 'system':
                message['role'] = 'user'
            
        # draw a red rectangle if this is the intermediate step
        regex = r"top_left\s*=\s*\((\d+,\s*\d+)\)|length\s*=\s*(\d+)"
        matches = re.findall(regex, localization_action)
        for match in matches:
            if match[0]:  # Matches top_left
                top_left = tuple(map(int, match[0].split(',')))
            if match[1]:  # Matches length
                length = int(match[1])
        screenshot_action = IPythonRun(code="take_screenshot()")
        image_path_output = await computer.run_ipython(screenshot_action)
        image_path = extract_image_path_from_output(image_path_output)
        screenshot = Image.open(image_path)
        cropped_img_rectangle, edge_distances, actual_rect_top_left = draw_rectangle(screenshot, last_top_left, last_length, top_left, length, 
                                                computer.screen_width, computer.screen_height)
        if cropped_img_rectangle:
            if isinstance(cropped_img_rectangle, str): # Initial cropped_img_dot is a str
                return cropped_img_rectangle
            else:
                cropped_img_rectangle, x_range, y_range = process_image_and_draw_grid(computer.intermediate_results_dir,
                                    cropped_img_rectangle, last_length,
                                    grid_offset=last_top_left)
                logger.info(f'x_range: {x_range}, y_range: {y_range}')
                image_url = encode_image(cropped_img_rectangle)
                dc_messages = dc_messages_initial + [{'role': 'user',
                                    'content': [{
                                                    "type": "text",
                                                    "text": LOCALIZATION_CHECK_RECTANGLE_PROMPT.format(item_to_click=item_to_click, 
                                                                                                        Location=Location, 
                                                                                                        left_distance = edge_distances['left'],
                                                                                                        right_distance = edge_distances['right'],
                                                                                                        bottom_distance = edge_distances['bottom'],
                                                                                                        top_distance = edge_distances['top'],
                                                                                                        x_range=x_range, 
                                                                                                        y_range=y_range)
                                                },
                                                {"type": "image_url",
                                                "image_url": {"url": f"data:image/png;base64,{image_url}",
                                                            "detail": "high"}}]}]
        current_action = f'localization(top_left=({int(actual_rect_top_left[0])},{int(actual_rect_top_left[1])}),length={length})'
        
    actions = []      
    feedback_times = 0                          
    # while not '<|command_correct|>' in response:
    while True:
        feedback_times += 1
        if feedback_times > 5:
            break
        whether_move = False
        dx, dy = 0, 0 
        for action in actions:
            action_lines = action.split("\n") 
            for line in action_lines:
                if 'move(' in line:
                    regex = r"direction\s*=\s*['\"](\w+)['\"]|distance\s*=\s*(\d+)"
                    matches = re.findall(regex, line)
                    direction, distance = None, 0 
                    for match in matches:
                        if match[0]: 
                            direction = str(match[0])
                        if match[1]: 
                            distance = int(match[1])
                    direction_map = {
                        "left": (-distance, 0),
                        "right": (distance, 0),
                        "up": (0, -distance),
                        "down": (0, distance)
                    }
                    if direction in direction_map:
                        dx += direction_map[direction][0]  
                        dy += direction_map[direction][1] 
                        whether_move = True  
        
        # If we need to move the rectangle/dot
        if whether_move:
            if draw_type == "dot":
                screenshot_action = IPythonRun(code="take_screenshot()")
                image_path_output = await computer.run_ipython(screenshot_action)
                image_path = extract_image_path_from_output(image_path_output)
                screenshot = Image.open(image_path)
                original_coordination = coordination
                coordination = (coordination[0] + dx, coordination[1] + dy)
                cropped_img_dot, edge_distances, actual_coordination = draw_dot(screenshot, last_top_left, last_length, coordination, 
                                            computer.screen_width, computer.screen_height)
                if cropped_img_dot:
                    if isinstance(cropped_img_dot, str):
                        dc_messages.append({'role': 'user',
                        'content': cropped_img_dot})
                        coordination = original_coordination # reset the coordination, because the action is not valid
                    else:
                        cropped_img_dot, x_range, y_range = process_image_and_draw_grid(computer.intermediate_results_dir, 
                                        cropped_img_dot, last_length, 
                                        grid_offset=last_top_left, draw_type="dot") 
                        image_url = encode_image(cropped_img_dot)
                        dc_messages = dc_messages_initial + [{'role': 'user',
                                        'content': [{
                                                        "type": "text",
                                                        "text": LOCALIZATION_CHECK_DOT_PROMPT.format(item_to_click=item_to_click, 
                                                                                                    Location=Location, 
                                                                                                    left_distance = edge_distances['left'],
                                                                                                    right_distance = edge_distances['right'],
                                                                                                    bottom_distance = edge_distances['bottom'],
                                                                                                    top_distance = edge_distances['top'],
                                                                                                    x_range=x_range, 
                                                                                                    y_range=y_range)
                                                    },
                                                    {"type": "image_url",
                                                    "image_url": {"url": f"data:image/png;base64,{image_url}",
                                                                "detail": "high"}}]}]    
                        current_action = f'localization_done({int(actual_coordination[0])},{int(actual_coordination[1])})' 
            elif draw_type == "rectangle":
                screenshot_action = IPythonRun(code="take_screenshot()")
                image_path_output = await computer.run_ipython(screenshot_action)
                image_path = extract_image_path_from_output(image_path_output)
                screenshot = Image.open(image_path)
                original_top_left = top_left
                top_left = (top_left[0] + dx, top_left[1] + dy)
                cropped_img_rectangle, edge_distances, actual_rect_top_left = draw_rectangle(screenshot, last_top_left, last_length, top_left, 
                                                    length, computer.screen_width, computer.screen_height)
                if cropped_img_rectangle:
                    if isinstance(cropped_img_rectangle, str): # cropped_img_dot is a str
                        dc_messages.append({'role': 'user',
                        'content': cropped_img_rectangle})
                        top_left = original_top_left # reset the top_left, because the action is not valid
                    else:
                        cropped_img_rectangle, x_range, y_range = process_image_and_draw_grid(computer.intermediate_results_dir,
                                            cropped_img_rectangle, last_length,
                                            grid_offset=last_top_left)
                        logger.info(f'x_range: {x_range}, y_range: {y_range}')
                        image_url = encode_image(cropped_img_rectangle)
                        dc_messages = dc_messages_initial + [{'role': 'user',
                                        'content': [{
                                                        "type": "text",
                                                        "text": LOCALIZATION_CHECK_RECTANGLE_PROMPT.format(item_to_click=item_to_click, 
                                                                                                            Location=Location, 
                                                                                                            left_distance=edge_distances['left'],
                                                                                                            right_distance=edge_distances['right'],
                                                                                                            bottom_distance=edge_distances['bottom'],
                                                                                                            top_distance=edge_distances['top'],
                                                                                                            x_range=x_range, y_range=y_range)
                                                    },
                                                    {"type": "image_url",
                                                    "image_url": {"url": f"data:image/png;base64,{image_url}",
                                                                "detail": "high"}}]}]
                        current_action = f'localization(top_left=({int(actual_rect_top_left[0])},{int(actual_rect_top_left[1])}),length={length})'
        
        # print_messages(dc_messages, "localizaiton_correction")
        response,_ = agent.llm.completion(messages=dc_messages, stop=['</localize>'])
        logger.info(f"Response in localizaiton_correction: {response}")
        if '<|command_correct|>' in response:
            break
        
        # Handle special cases: no action is avaliable
        actions = [parse_action(response)]
        if len(actions) == 0:
            break
        dc_messages.append({'role': 'assistant', 'content': response})
    return current_action
