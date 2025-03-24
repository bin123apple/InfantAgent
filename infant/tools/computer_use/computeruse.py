import os
import time
import subprocess
from PIL import ImageGrab

from infant.tools.util import update_pwd_decorator

@update_pwd_decorator
def get_mouse_position():
    """
    Get the current mouse position using xdotool.
    Returns:
        tuple: (x, y) coordinates of the mouse.
    """
    result = subprocess.run("xdotool getmouselocation --shell", shell=True, stdout=subprocess.PIPE)
    output = result.stdout.decode("utf-8")
    # Parse the output to extract x and y positions
    lines = output.strip().split("\n")
    x = int(lines[0].split("=")[1])  # Extract x-coordinate
    y = int(lines[1].split("=")[1])  # Extract y-coordinate
    return x, y

@update_pwd_decorator
def take_screenshot(command: str | None = None, top_left: tuple | None = None, length: int | None = None) -> str:
    """
    Captures a screenshot, adds a coordinate system with dashed deep red lines, larger labels,
    and marks the mouse position with an enlarged red dot. Each intersection of the coordinate
    Args:
        command: str: The command that triggered the screenshot.
        top_left: tuple: (x, y) coordinates of the top-left corner of the region to capture.
        length: int: The length of the side of the square region to capture.
    Returns:
        str: The path to the saved screenshot.
    """
    # Constants
    time.sleep(2)
    screenshot_dir = "/workspace/screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    timestamp = int(time.time())
    screenshot_path = f"{screenshot_dir}/{timestamp}.png"

    # Get screen resolution
    screen_width, screen_height = ImageGrab.grab().size

    # Define the capture region
    if top_left and length:
        region = (
            int(top_left[0]),
            int(top_left[1]),
            min(int(top_left[0]) + int(length), screen_width),
            min(int(top_left[1]) + int(length * 0.75), screen_height),
        )
        img = ImageGrab.grab(bbox=region)
        img.save(screenshot_path)
        # time.sleep(2)
        print(f"<Screenshot saved at> {screenshot_path}")
        length = region[2] - region[0]
    else:
        img = ImageGrab.grab()
        img.save(screenshot_path)
        # time.sleep(2)
        print(f"<Screenshot saved at> {screenshot_path}")
        length = screen_width
        
@update_pwd_decorator
def mouse_left_click(x, y, button="left"):
    """
    Simulates a mouse click at the specified coordinates.
    Args:
        x (int): x-coordinate.
        y (int): y-coordinate.
        button (str): The mouse button to click ("left" or "right
    Returns:
        None (Will take a screenshot)
    """
    if x != -1 and y != -1:
        button_code = 1 if button == "left" else 3
        subprocess.run(f"xdotool mousemove {x} {y} click {button_code}", shell=True)
        time.sleep(1)
        take_screenshot(f'mouse_left_click({x}, {y})')
    else:
        print('Please provide a more detailed description of where you want to click.')

@update_pwd_decorator
def mouse_double_click(x, y, button="left"):
    """
    Simulates a double-click at the specified coordinates.
    Args:
        x (int): x-coordinate.
        y (int): y-coordinate.
        button (str): The mouse button to click ("left" or "right)
    Returns:
        None (Will take a screenshot)
    """
    if x != -1 and y != -1:
        button_code = 1 if button == "left" else 3
        subprocess.run(f"xdotool mousemove {x} {y} click {button_code} click {button_code}", shell=True)
        time.sleep(1)
        take_screenshot(f'mouse_double_click({x}, {y})')
    else:
        print('Please provide a more detailed description of where you want to double-click.')

@update_pwd_decorator
def mouse_right_click(x, y):
    """
    Simulates a right mouse click at the specified coordinates.
    Args:
        x (int): x-coordinate.
        y (int): y-coordinate.
    Returns:
        None (Will take a screenshot)
    """
    if x != -1 and y != -1:
        subprocess.run(f"xdotool mousemove {x} {y} click 3", shell=True)
        time.sleep(1)
        take_screenshot(f'mouse_right_click({x}, {y})')
    else:
        print('Please provide a more detailed description of where you want to right-click.')

@update_pwd_decorator
def mouse_move(x, y):
    """
    Moves the mouse to the specified coordinates.
    Args:
        x (int): x-coordinate.
        y (int): y-coordinate.
    Returns:
        None (Will take a screenshot)
    """
    if x != -1 and y != -1:
        subprocess.run(f"xdotool mousemove {x} {y}", shell=True)
        time.sleep(1)
        take_screenshot(f'mouse_move({x}, {y})')
    else:
        print('Please provide a more detailed description of where you want to move the mouse.')

@update_pwd_decorator
def mouse_scroll(direction="up", amount=1):
    """
    Simulates a mouse scroll up or down.
    Args:
        direction (str): The direction to scroll ("up" or "down").
        amount (int): The number of scroll steps to take.
    Returns:
        None (Will take a screenshot
    """
    button_code = 4 if direction == "up" else 5
    for _ in range(amount):
        subprocess.run(f"xdotool click {button_code}", shell=True)
        time.sleep(1)
    take_screenshot(f'mouse_scroll({direction}, {amount})')

@update_pwd_decorator
def type_text(text: str):
    """
    Simulates typing text.
    Args:
        text (str): The text to type.
    Returns:
        None (Will take a screenshot)
    """
    time.sleep(1)
    subprocess.run(f'xdotool type "{text}"', shell=True)
    sanitized_text = text.replace('/', '_')
    time.sleep(1)
    take_screenshot(f'type_text({sanitized_text})')

@update_pwd_decorator
def press_key(key: str):
    """
    Simulates pressing a specific key.
    Args:
        key (str): The key to press.
    Returns:
        None (Will take a screenshot)
    """
    subprocess.run(f"xdotool key {key}", shell=True)
    sanitized_key = key.replace('/', '_')
    time.sleep(1)
    take_screenshot(f'press_key({sanitized_key})')
    
@update_pwd_decorator
def press_key_combination(keys: str):
    """
    Simulates pressing a combination of keys.
    Args:
        keys (str): The key combination to press (e.g., "ctrl+alt+t").
    Returns:
        None (Will take a screenshot)
    """
    subprocess.run(f"xdotool key {keys}", shell=True)
    sanitized_keys = keys.replace('/', '_')
    time.sleep(1)
    take_screenshot(f'press_key_combination({sanitized_keys})')

@update_pwd_decorator
def open_application(app_name):
    """
    Opens a specific application using xdotool.
    Args:
        app_name (str): The name of the application to open.
    Returns:
        None (Will take a screenshot)
    """
    # Simulate pressing the "Super" key to open the application launcher
    subprocess.run("xdotool key super", shell=True)
    time.sleep(1)
    
    # Type the application name in the search bar
    subprocess.run(f"xdotool type '{app_name}'", shell=True)
    time.sleep(1)
    
    # Press "Enter" to open the application
    subprocess.run("xdotool key Return", shell=True)
    print(f"Opening {app_name}...")
    time.sleep(2)
    take_screenshot(f'open_application({app_name})')

@update_pwd_decorator
def mouse_drag(x_start, y_start, x_end, y_end, button="left"):
    """
    Simulates dragging the mouse from one position to another with smooth movements.    
    Mouse drag may not be very accurate in Linux as the screen is sperated into multiple cells.
    Args:
        x_start (int): x-coordinate of the starting position.
        y_start (int): y-coordinate of the starting position.
        x_end (int): x-coordinate of the ending position.
        y_end (int): y-coordinate of the ending position.
        button (str): The mouse button to drag ("left" or "right).
    Returns:
        None (Will take a screenshot)
    """
    
    try:
        button_code = 1 if button == "left" else 3
        
        # Move to start position
        subprocess.run(f"xdotool mousemove {x_start} {y_start}", shell=True, check=True)
        time.sleep(0.2)
        
        # Press the mouse button
        subprocess.run(f"xdotool mousedown {button_code}", shell=True, check=True)
        time.sleep(0.2)
        
        mouse_pos_x, mouse_pos_y = get_mouse_position()
        print(f"Before drag: Mouse position: {mouse_pos_x}, {mouse_pos_y}")
        
        # Compute incremental steps for smooth movement
        # Move horizontally first
        x_step = x_end - x_start
        for i in range(1, abs(x_step) + 1):
            if x_step > 0:
                intermediate_x = int(x_start + i)
            else:
                intermediate_x = int(x_start - i)
            subprocess.run(f"xdotool mousemove {intermediate_x} {y_start}", shell=True, check=True)
        
        # Move vertically next
        y_step = y_end - y_start
        for i in range(1, abs(y_step) + 1):
            if y_step > 0:
                intermediate_y = int(y_start + i)
            else:
                intermediate_y = int(y_start - i)
            subprocess.run(f"xdotool mousemove {x_end} {intermediate_y}", shell=True, check=True)
        
        # Release the mouse button
        subprocess.run(f"xdotool mouseup {button_code}", shell=True, check=True)
        time.sleep(0.2)
        
        mouse_pos_x, mouse_pos_y = get_mouse_position()
        print(f"After drag: Mouse position: {mouse_pos_x}, {mouse_pos_y}")
        
        # Optionally capture a screenshot
        take_screenshot(f'mouse_drag({x_start}, {y_start}, {x_end}, {y_end})')
    except subprocess.CalledProcessError as e:
        print(f"Error executing xdotool command: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

@update_pwd_decorator
def download(url: str, save_dir: str = "/workspace") -> None:
    """
    Download a file from the given URL to the specified directory using wget.

    Args:
        url (str): The URL of the file to download.
        save_dir (str): The directory to save the downloaded PDF.
    """
    try:
        subprocess.run(["wget", "-P", save_dir, url], check=True)
        print(f"Downloaded file to {save_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to download file from {url}")
        print("Error:", e)