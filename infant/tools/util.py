import os
import re
import chardet
import functools
import mimetypes
import subprocess
from typing import Optional
from inspect import signature

CURRENT_FILE: str | None = None
CURRENT_LINE = 1
WINDOW = 100

ENABLE_AUTO_LINT = os.getenv('ENABLE_AUTO_LINT', 'true').lower() == 'true'
EXCEL_EXTENSIONS = {".xls", ".xlsx"}
# This is also used in unit tests!
MSG_FILE_UPDATED = '[File updated. Please review the changes and make sure they are correct (correct indentation, no duplicate lines, etc). Edit the file again if necessary.]'

def update_pwd_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        old_pwd = os.getcwd()
        jupyter_pwd = os.environ.get('JUPYTER_PWD', None)
        if jupyter_pwd:
            os.chdir(jupyter_pwd)
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(old_pwd)

    return wrapper

def _is_valid_filename(file_name) -> bool:
    if not file_name or not isinstance(file_name, str) or not file_name.strip():
        return False
    invalid_chars = '<>:"/\\|?*'
    if os.name == 'nt':  # Windows
        invalid_chars = '<>:"/\\|?*'
    elif os.name == 'posix':  # Unix-like systems
        invalid_chars = '\0'

    for char in invalid_chars:
        if char in file_name:
            return False
    return True

def _is_valid_path(path) -> bool:
    if not path or not isinstance(path, str):
        return False
    try:
        return os.path.exists(os.path.normpath(path))
    except PermissionError:
        return False

def _create_paths(file_name) -> bool:
    try:
        dirname = os.path.dirname(file_name)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        return True
    except PermissionError:
        return False

def _check_current_file(file_path: str | None = None) -> bool:
    global CURRENT_FILE
    if not file_path:
        file_path = CURRENT_FILE
    if not file_path or not os.path.isfile(file_path):
        raise ValueError('No file open. Use the open_file function first.')
    return True

def _clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

def match_str(my_string, my_list, line_number):
    '''
    Match a string from a list.
    If no match, try to use the fuzzy matching mode
    '''
    closest_index = None
    closest_distance = float('inf')
    
    if my_string == '':
        return closest_index
    
    for i, element in enumerate(my_list):
        if my_string == element.replace('\n',''):
            distance = abs(i + 1 - line_number)
            if distance < closest_distance:
                closest_index = i
                closest_distance = distance

    if closest_index is None:
        for i, element in enumerate(my_list):
            if my_string.strip() in element.strip():
                distance = abs(i + 1 - line_number)
                if distance < closest_distance:
                    closest_index = i
                    closest_distance = distance

    if closest_index is not None:
        return closest_index
    else:
        return None

def _lint_file(file_path: str) -> tuple[Optional[str], Optional[int]]:
    """
    Lint the file at the given path and return a tuple with a boolean indicating if there are errors,
    and the line number of the first error, if any.

    Returns:
        tuple[str, Optional[int]]: (lint_error, first_error_line_number)
    """

    if file_path.endswith('.py'):
        # Define the flake8 command with selected error codes
        command = [
            'flake8',
            '--isolated',
            '--select=F821,F822,F831,E112,E113,E999,E902',
            file_path,
        ]

        # Run the command using subprocess and redirect stderr to stdout
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode == 0:
            # Linting successful. No issues found.
            return None, None

        # Extract the line number from the first error message
        error_message = result.stdout.decode().strip()
        lint_error = 'ERRORS:\n' + error_message
        first_error_line = None
        for line in error_message.splitlines(True):
            if line.strip():
                # The format of the error message is: <filename>:<line>:<column>: <error code> <error message>
                parts = line.split(':')
                if len(parts) >= 2:
                    try:
                        first_error_line = int(parts[1])
                        break
                    except ValueError:
                        # Not a valid line number, continue to the next line
                        continue

        return lint_error, first_error_line

    # Not a python file, skip linting
    return None, None

def _cur_file_header(CURRENT_FILE, total_lines) -> str:
    if not CURRENT_FILE:
        return ''
    return f'[File: {os.path.abspath(CURRENT_FILE)} ({total_lines} lines total)]\n'

def search_function_line_number(file_path: str, function_signature: str) -> tuple[int | None, int | None]:
    """
    Args:
        file_path (str): The path of the file to search.
        function_signature (str): The function name to search for.
        
    Returns:
        tuple[int | None, int | None]: A tuple (start_line, end_line) indicating the lines where the function is defined.
            If not found, returns (None, None) and prints an error message.
    """
    try:
        with open(file_path, 'r') as file:
            code_lines = file.readlines()
        
        start_line_number = None
        end_line_number = None
        header_end_line = None 
        indent_level = None
        
        pattern = re.compile(rf'^\s*def\s+{re.escape(function_signature)}\b')
        
        for index, line in enumerate(code_lines):
            if pattern.match(line):
                start_line_number = index + 1  
                header_lines = [line]
                header_end_line = index
                if not line.rstrip().endswith(':'):
                    for j in range(index + 1, len(code_lines)):
                        header_lines.append(code_lines[j])
                        if code_lines[j].rstrip().endswith(':'):
                            header_end_line = j
                            break
                indent_level = len(code_lines[index]) - len(code_lines[index].lstrip())
                
                for k in range(header_end_line + 1, len(code_lines)):
                    current_line = code_lines[k]
                    if current_line.strip() == '':
                        continue
                    current_indent = len(current_line) - len(current_line.lstrip())
                    if current_indent <= indent_level:
                        end_line_number = k
                        break
                if end_line_number is None:
                    end_line_number = len(code_lines)
                return (start_line_number, end_line_number)
        
        print(f"Function '{function_signature}' not found in the file '{file_path}'.")
        print("Please check the function signature and try again. NOTE: The function signature should only include the function name.")
        return None, None
    except FileNotFoundError:
        raise Exception(f"File '{file_path}' not found.")
    except Exception as e:
        raise Exception(f"An error occurred: {e}")

def _clamp(value, min_value, max_value):
    return max(min(value, max_value), min_value)

def _print_window(file_path, targeted_line, WINDOW, return_str=False):
    global CURRENT_LINE
    _check_current_file(file_path)
    with open(file_path) as file:
        content = file.read()

        # Ensure the content ends with a newline character
        if not content.endswith('\n'):
            content += '\n'

        lines = content.splitlines(True)  # Keep all line ending characters
        total_lines = len(lines)

        # cover edge cases
        CURRENT_LINE = _clamp(targeted_line, 1, total_lines)
        half_window = max(1, WINDOW // 2)

        # Ensure at least one line above and below the targeted line
        start = max(1, CURRENT_LINE - half_window)
        end = min(total_lines, CURRENT_LINE + half_window)

        # Adjust start and end to ensure at least one line above and below
        if start == 1:
            end = min(total_lines, start + WINDOW - 1)
        if end == total_lines:
            start = max(1, end - WINDOW + 1)

        output = ''

        # only display this when there's at least one line above
        if start > 1:
            output += f'({start - 1} more lines above)\n'
        for i in range(start, end + 1):
            _new_line = f'{i}|{lines[i-1]}'
            if not _new_line.endswith('\n'):
                _new_line += '\n'
            output += _new_line
        if end < total_lines:
            output += f'({total_lines - end} more lines below)\n'
        output = output.rstrip()

        if return_str:
            return output
        else:
            print(output)

def is_text_file(file_path):
    """
    Determine if a file is a text file based on its content and extension.
    """
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith("text"):
            return True

        with open(file_path, "rb") as f:
            raw_data = f.read(2048)
            if b"\x00" in raw_data: 
                return False
            result = chardet.detect(raw_data)
            encoding = result["encoding"]

        return bool(encoding)
    except Exception as e:
        print(f"Error detecting file type: {e}")
        return False  

def make_document():
    __all__ = [
        # file operation
        'open_file',
        'goto_line',
        'scroll_down',
        'scroll_up',
        'create_file',
        'append_file',
        'edit_file',
        'search_dir',
        'search_file',
        'find_file',
        'replace_function',
        'search_function',
        # readers
        'parse_pdf',
        'parse_docx',
        'parse_latex',
        'parse_pptx',
        # tools
        'parse_audio',
        'parse_video',
        'parse_image',
        # MK operations
        'take_screenshot',
        'mouse_left_click',
        'mouse_right_click',
        'mouse_double_click',
        'mouse_move',
        'mouse_scroll',
        'type_text',
        'press_key',
        'open_application',
        'mouse_drag',
        'mouse_right_click',
        'localization',
    ]

    document = ''
    for func_name in __all__:
        func = globals()[func_name]

        cur_doc = func.__doc__
        # remove indentation from docstring and extra empty lines
        cur_doc = '\n'.join(filter(None, map(lambda x: x.strip(), cur_doc.split('\n'))))
        # now add a consistent 4 indentation
        cur_doc = '\n'.join(map(lambda x: ' ' * 4 + x, cur_doc.split('\n')))

        fn_signature = f'{func.__name__}' + str(signature(func))
        document += f'{fn_signature}:\n{cur_doc}\n\n'
    return document