import os
from typing import Optional
from infant.tools.util import update_pwd_decorator, search_function_line_number 
from infant.tools.util import CURRENT_FILE
from infant.tools.file_reader.filereader import open_file

@update_pwd_decorator
def search_content(file_path: str, content: str) -> list[tuple[int, int]]:
    """
    Searches for the given content in the specified file and opens the file at the first match.
    Args:
        file_path (str): The path of the file to search.
        content (str): The content to search for.
    Returns:
        list[tuple[int, int]]: A list of tuples containing the start and end line numbers of the matches.
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the content is empty.
    """
    try:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        line_numbers = []
        line = 1
        for ch in text:
            line_numbers.append(line)
            if ch == "\n":
                line += 1

        spans: list[tuple[int, int]] = []
        start = 0
        while True:
            idx = text.find(content, start)
            if idx == -1:
                break
            end_idx = idx + len(content) - 1
            spans.append((line_numbers[idx], line_numbers[end_idx]))
            start = idx + 1

        if not spans:
            print(f"No matches for the given content in '{file_path}'.")
            return

        for i, (start_line, end_line) in enumerate(spans):
            print(f"Match {i + 1}: Lines {start_line} to {end_line}")
            mid_line = (start_line + end_line) // 2
            context_lines = end_line - start_line + 5
            open_file(path=file_path, line_number=mid_line, context_lines=context_lines)

        return

    except Exception as e:
        raise e


@update_pwd_decorator
def search_function(file_path: str, function_signature: str) -> str:
    """
    Args:
        file_path (str): The path of the file to search.
        function_signature (str): The signature of the function to search for.

    Returns:
        str: The code of the function if found, or an error message if not found.
    """
    try:
        if not file_path.endswith('.py'):
            raise ValueError(f"search_function only supports python file, but got {file_path}")
        start_line_number, end_line_number = search_function_line_number(file_path, function_signature)
        if start_line_number is None or end_line_number is None:
            print(f"Can not match '{function_signature}'. Possible reasons:\n"
                  f"1. The code style of file '{file_path}' is not supported, or\n"
                  f"2. The function signature is incorrect (please provide only the function name).")
            return f"search_function does not support this file type or function definition style."
        context_lines = end_line_number - start_line_number + 1
        line_number = (end_line_number + start_line_number) // 2
        open_file(path = file_path, line_number = line_number, context_lines = context_lines)
    except Exception as e:
        raise e

@update_pwd_decorator
def search_dir(search_term: str, dir_path: str = './') -> None:
    """Searches for search_term in all files in dir. If dir is not provided, searches in the current directory.

    Args:
        search_term: str: The term to search for.
        dir_path: Optional[str]: The path to the directory to search.
    """
    if not os.path.isdir(dir_path):
        raise FileNotFoundError(f'Directory {dir_path} not found')
    matches = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.startswith('.'):
                continue
            file_path = os.path.join(root, file)
            with open(file_path, 'r', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    if search_term in line:
                        matches.append((file_path, line_num, line.strip()))

    if not matches:
        print(f'No matches found for "{search_term}" in {dir_path}')
        return

    num_matches = len(matches)
    num_files = len(set(match[0] for match in matches))

    if num_files > 100:
        print(
            f'More than {num_files} files matched for "{search_term}" in {dir_path}. Please narrow your search.'
        )
        return

    print(f'[Found {num_matches} matches for "{search_term}" in {dir_path}]')
    for file_path, line_num, line in matches:
        print(f'{file_path} (Line {line_num}): {line}')
    print(f'[End of matches for "{search_term}" in {dir_path}]')


@update_pwd_decorator
def search_file(search_term: str, file_path: Optional[str] = None) -> None:
    """Searches for search_term in file. If file is not provided, searches in the current open file.

    Args:
        search_term: str: The term to search for.
        file_path: Optional[str]: The path to the file to search.
    """
    global CURRENT_FILE
    if file_path is None:
        file_path = CURRENT_FILE
    if file_path is None:
        raise FileNotFoundError(
            'No file specified or open. Use the open_file function first.'
        )
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f'File {file_path} not found')

    matches = []
    with open(file_path) as file:
        for i, line in enumerate(file, 1):
            if search_term in line:
                matches.append((i, line.strip()))

    if matches:
        print(f'[Found {len(matches)} matches for "{search_term}" in {file_path}]')
        for match in matches:
            print(f'Line {match[0]}: {match[1]}')
        print(f'[End of matches for "{search_term}" in {file_path}]')
    else:
        print(f'[No matches found for "{search_term}" in {file_path}]')

@update_pwd_decorator
def find_file(file_name: str, dir_path: str = './') -> None:
    """Finds all files with the given name in the specified directory.

    Args:
        file_name: str: The name of the file to find.
        dir_path: Optional[str]: The path to the directory to search.
    """
    if not os.path.isdir(dir_path):
        raise FileNotFoundError(f'Directory {dir_path} not found')

    matches = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file_name in file:
                matches.append(os.path.join(root, file))

    if matches:
        print(f'[Found {len(matches)} matches for "{file_name}" in {dir_path}]')
        for match in matches:
            print(f'{match}')
        print(f'[End of matches for "{file_name}" in {dir_path}]')
    else:
        print(f'[No matches found for "{file_name}" in {dir_path}]')