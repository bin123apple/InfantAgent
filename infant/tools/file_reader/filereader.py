import os
import fitz
import time
import pandas as pd
from typing import List, Tuple

from infant.tools.util import update_pwd_decorator, CURRENT_FILE, CURRENT_LINE, WINDOW, EXCEL_EXTENSIONS
from infant.tools.util import _cur_file_header, _print_window, _check_current_file, _clamp, is_text_file

@update_pwd_decorator
def open_file(
    path: str, line_number: int | None = 1, context_lines: int | None = 150
) -> None:
    """
    Opens the file at the given path in the editor. If line_number is provided, the window will be moved to include that line.
    It only shows the first 100 lines by default! Max `context_lines` supported is 2000, use `scroll up/down`
    to view the file if you want to see more.

    Args:
        path: str: The path to the file to open, preferredly absolute path.
        line_number: int | None = 1: The line number to move to. Defaults to 1.
        context_lines: int | None = 100: Only shows this number of lines in the context window (usually from line 1), with line_number as the center (if possible). Defaults to 100.
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW

    if not os.path.isfile(path):
        raise FileNotFoundError(f"File {path} not found")

    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in EXCEL_EXTENSIONS:
        CURRENT_FILE = os.path.abspath(path)
        df = pd.read_excel(CURRENT_FILE)
        print(f"Opening Excel file: {CURRENT_FILE}")
        print(f"Displaying first {context_lines} rows:")
        print(df.head(context_lines))
        return
    elif not is_text_file(path):
        raise ValueError(f"Unsupported binary file: {ext}. Only text files are supported.")

    CURRENT_FILE = os.path.abspath(path)
    with open(CURRENT_FILE, encoding="utf-8") as file:
        total_lines = max(1, sum(1 for _ in file))

    if not isinstance(line_number, int) or line_number < 1 or line_number > total_lines:
        raise ValueError(f"Line number must be between 1 and {total_lines}")
    CURRENT_LINE = line_number

    # Override WINDOW with context_lines
    if context_lines is None or context_lines < 1:
        context_lines = 150
    WINDOW = _clamp(context_lines, 1, 2000)

    output = _cur_file_header(CURRENT_FILE, total_lines)
    output += _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW, return_str=True)
    print(output)
    
@update_pwd_decorator
def goto_line(line_number: int) -> None:
    """
    Moves the window to show the specified line number.

    Args:
        line_number: int: The line number to move to.
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW
    _check_current_file()

    with open(str(CURRENT_FILE)) as file:
        total_lines = max(1, sum(1 for _ in file))
    if not isinstance(line_number, int) or line_number < 1 or line_number > total_lines:
        raise ValueError(f'Line number must be between 1 and {total_lines}')

    CURRENT_LINE = _clamp(line_number, 1, total_lines)

    output = _cur_file_header(CURRENT_FILE, total_lines)
    output += _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW, return_str=True)
    print(output)

@update_pwd_decorator
def scroll_down() -> None:
    """Moves the window down by 100 lines.

    Args:
        None
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW
    _check_current_file()

    with open(str(CURRENT_FILE)) as file:
        total_lines = max(1, sum(1 for _ in file))
    CURRENT_LINE = _clamp(CURRENT_LINE + WINDOW, 1, total_lines)
    output = _cur_file_header(CURRENT_FILE, total_lines)
    output += _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW, return_str=True)
    print(output)
    
@update_pwd_decorator
def scroll_up() -> None:
    """Moves the window up by 100 lines.

    Args:
        None
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW
    _check_current_file()

    with open(str(CURRENT_FILE)) as file:
        total_lines = max(1, sum(1 for _ in file))
    CURRENT_LINE = _clamp(CURRENT_LINE - WINDOW, 1, total_lines)
    output = _cur_file_header(CURRENT_FILE, total_lines)
    output += _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW, return_str=True)
    print(output)
    
@update_pwd_decorator
def parse_pdf(pdf_path: str, page: int) -> fitz.Pixmap:
    """
    Captures a high-resolution screenshot of the entire specified page of the PDF (fixed zoom = 5.0)
    and returns the screenshot as a PyMuPDF Pixmap object.
    
    Parameters:
        pdf_path (str): The path to the PDF file.
        page (int): The page number to process (1-indexed).
        output_path (str, optional): The file path to save the screenshot. If provided, the image will be saved.
    
    Returns:
        pix (fitz.Pixmap): The screenshot as a PyMuPDF Pixmap object.
    """
    # Open the PDF using PyMuPDF
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    if page < 1 or page > total_pages:
        print(f"Page number {page} is out of range. Total pages: {total_pages}")
        return None

    # Load the specified page (PyMuPDF uses 0-indexed page numbers)
    pdf_page = doc.load_page(page - 1)
    
    # Create a transformation matrix with a fixed zoom factor of 5.0 for high-resolution output
    mat = fitz.Matrix(5.0, 5.0)
    pix = pdf_page.get_pixmap(matrix=mat)
    
    # Save the screenshot if an output path is provided
    screenshot_dir = "/workspace/screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    timestamp = int(time.time())
    screenshot_path = f"{screenshot_dir}/{timestamp}.png"
    pix.save(screenshot_path)
    print('If the PDF file has page numbers indicated at the bottom, please refer to those page numbers as the standard. Note that they may differ from the page numbers mentioned in our instructions, as the initial pages of the PDF might include a table of contents or a cover page.')
    print(f"<Screenshot saved at> {screenshot_path}")
    
@update_pwd_decorator
def parse_figure(figure_path: str):
    """
    Parse a figure from the given path and return its dimensions or trigger appropriate handlers.
    
    Args:
        figure_path (str): The path to the figure file.
        
    Returns:
        None
    """
    ext = os.path.splitext(figure_path)[-1].lower()

    # Image file types (you can extend this list as needed)
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}

    if ext in image_extensions:
        print(f"<Screenshot saved at> {figure_path}")
    elif ext == '.pdf':
        print(f'{figure_path} is not a supported figure type. '
            'Please use `parse_pdf(pdf_path: str, page: int)` command to view the PDF.')
    else:
        print(f'{figure_path} is not a supported figure type.\n'
              'Please use `open_file(path: str, line_number: int | None = 1, context_lines: int | None = 150)` ' 
              'command to view it.')
    

@update_pwd_decorator
def zoom_pdf(pdf_path: str, page: int, region: tuple):
    """
    捕获PDF中指定页中某一特定区域的高分辨率截图，用于清晰查看局部图片。
    
    参数:
        pdf_path (str): PDF文件路径。
        page (int): 需要处理的页码（从1开始）。
        region (tuple): 指定区域的元组，格式为 (x0, y0, x1, y1)，坐标使用PDF的坐标系。
        zoom (float): 渲染时的缩放因子，默认值为5.0。
        output_path (str, optional): 如果提供，则保存图片到此路径。
    
    返回:
        pix (fitz.Pixmap): 截图的Pixmap对象。
    """
    # 打开PDF文件
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    if page < 1 or page > total_pages:
        print(f"Page number {page} is out of range. Total pages: {total_pages}")
        return None

    # 加载指定页（页码从0开始）
    pdf_page = doc.load_page(page - 1)
    
    # 创建缩放矩阵
    mat = fitz.Matrix(5, 5)
    
    # 使用指定区域进行裁剪（clip参数）
    clip_rect = fitz.Rect(*region)
    pix = pdf_page.get_pixmap(matrix=mat, clip=clip_rect)
    
    screenshot_dir = "/workspace/screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    timestamp = int(time.time())
    screenshot_path = f"{screenshot_dir}/{timestamp}.png"
    pix.save(screenshot_path)
    print(f"<Screenshot saved at> {screenshot_path}")