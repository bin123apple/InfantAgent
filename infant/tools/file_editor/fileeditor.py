import os
import re
import shutil
import tempfile

from infant.tools.util import update_pwd_decorator, _print_window, _lint_file, match_str, search_function_line_number 
from infant.tools.util import _is_valid_filename, _is_valid_path, _create_paths
from infant.tools.util import MSG_FILE_UPDATED, ENABLE_AUTO_LINT, WINDOW, CURRENT_FILE, CURRENT_LINE
from infant.tools.file_reader.filereader import open_file


@update_pwd_decorator
def create_file(filename: str, content: str | None) -> None:
    """Creates and opens a new file with the given name.
    And add the content to the file if content is not None.

    Args:
        filename: str: The name of the file to create.
    """
    if os.path.exists(filename):
        raise FileExistsError(f"File '{filename}' already exists.")

    if content is not None:
        with open(filename, 'a') as file:
            file.write(content)
    else:
        with open(filename, 'w') as file:
            file.write('\n')
    open_file(filename)
    print(f'[File {filename} created.]')

@update_pwd_decorator
def replace_function(
    file_name: str, 
    function_to_replace: str,
    new_code: str
    ) -> None:
    """Replace some lines inside the function 
    (This is used to avoid some potential wrong line numberproblems in edit_file function)

    Args:
        filename: str: The name of the file to create.
        code_to_replace: str: The original code that will be replaced
        new_code: str: new code that will be used
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW

    # Check file
    
    if not _is_valid_filename(file_name):
        
        raise FileNotFoundError('Invalid file name.')

    if not _is_valid_path(file_name):
        
        raise FileNotFoundError('Invalid path or file name.')

    if not _create_paths(file_name):
        
        raise PermissionError('Could not access or create directories.')

    if not os.path.isfile(file_name):
        
        raise FileNotFoundError(f'File {file_name} not found.')

    # Use a temporary file to write changes
    temp_file_path = ''
    src_abs_path = os.path.abspath(file_name)
    first_error_line = None
    try:
        # # lint the original file
        if ENABLE_AUTO_LINT:
            origianl_lint_error, origianl_first_error_line = _lint_file(file_name)      
              
        with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
            temp_file_path = temp_file.name

            # Read the original file and check if empty and for a trailing newline
            with open(file_name) as original_file:
                file_content = original_file.read()   
                start_line, end_line = search_function_line_number(file_name, function_to_replace)
                if start_line is None or end_line is None:
                    return
                def replace_code_block(file_content, start_line, end_line, new_code):
                    file_lines = file_content.splitlines()
                    file_lines[start_line-1:end_line] = [new_code]
                    updated_file_content = "\n".join(file_lines)
                    return updated_file_content
                
                # replace the code block
                updated_file_content = replace_code_block(file_content, start_line, end_line, new_code)
                
            # Write the new content to the temporary file
            temp_file.write(updated_file_content)

        # Replace the original file with the temporary file atomically
        shutil.move(temp_file_path, src_abs_path)
        
        # find the first different line
        original_lines = file_content.splitlines()
        updated_lines = updated_file_content.splitlines()
        
        new_code_line = None
        for index, (original, updated) in enumerate(zip(original_lines, updated_lines), start=1):
            if original != updated:
                new_code_line = index
                break
                
        # Modified lines
        m_lines = len(new_code.splitlines())
        
        # middle screen
        window = m_lines + 10
        # print(f"window: {window}")
        if new_code_line is not None:
            middle_screen = new_code_line
        else:
            middle_screen = None
            print("The new code is exactly the same as the original code. You should use a different code and try again!")
        # print(f"middle_screen: {middle_screen}")
        
        
        # Handle linting
        if ENABLE_AUTO_LINT:
            # BACKUP the original file
            original_file_backup_path = os.path.join(
                os.path.dirname(file_name),
                f'.backup.{os.path.basename(file_name)}',
            )
            with open(original_file_backup_path, 'w') as f:
                 f.write(file_content)

            lint_error, first_error_line = _lint_file(file_name)

            # Select the errors caused by the modification
            def extract_last_part(line):
                parts = line.split(':')
                if len(parts) > 1:
                    return parts[-1].strip()
                return line.strip()

            def subtract_strings(str1, str2) -> str:
                lines1 = str1.splitlines()
                lines2 = str2.splitlines()
                
                last_parts1 = [extract_last_part(line) for line in lines1]
                
                remaining_lines = [line for line in lines2 if extract_last_part(line) not in last_parts1]

                result = '\n'.join(remaining_lines)
                return result
            if origianl_lint_error:
                if lint_error is not None:
                    lint_error = subtract_strings(origianl_lint_error, lint_error)
                if lint_error == "":
                    lint_error = None
                    first_error_line = None
                                                           
            if lint_error is not None:
                
                if first_error_line is not None:
                    CURRENT_LINE = middle_screen
                print(
                    '[Your proposed edit has introduced new syntax error(s). Please understand the errors and retry your edit command.]'
                )
                
                print('[This is how your edit would have looked if applied]')
                print('-------------------------------------------------')
                _print_window(file_name, CURRENT_LINE, window)
                print('-------------------------------------------------\n')

                print('[This is the original code before your edit]')
                print('-------------------------------------------------')
                _print_window(original_file_backup_path, CURRENT_LINE, window)
                print('-------------------------------------------------')

                print(
                    'Your changes have NOT been applied. Please fix your edit command and try again based on the following error messages.\n'
                    f'{lint_error}\n'
                    'You may need to do one or several of the following:\n'
                    '1) Specify the correct code block that you want to modify;\n' 
                    '2) Make sure that the Args position is correct (the 2nd arg is the original code that will be replaced and the 3rd arg is the new code that will be used);\n' 
                    '3) Choose another command (Such as edit_file(file_name, start, start_str end, end_str, content) command).\n'
                    '4) Use open_file(path, line_number, context_lines) command to check the details of where you want to modify and improve your command.\n'
                    'DO NOT re-run the same failed edit command. Running it again will lead to the same error.'
                )

                # recover the original file
                with open(original_file_backup_path) as fin, open(
                    file_name, 'w'
                ) as fout:
                    fout.write(fin.read())
                os.remove(original_file_backup_path)
                return

    except FileNotFoundError as e:
        
        print(f'File not found: {e}')
    except IOError as e:
        
        print(f'An error occurred while handling the file: {e}')
    except ValueError as e:
        
        print(f'Invalid input: {e}')
    except Exception as e:
        
        # Clean up the temporary file if an error occurs
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        print(f'An unexpected error occurred: {e}')
        raise e

    # Update the file information and print the updated content
    with open(file_name, 'r', encoding='utf-8') as file:
        n_total_lines = max(1, len(file.readlines()))
    if first_error_line is not None and int(first_error_line) > 0:
        CURRENT_LINE = first_error_line
    else:
        CURRENT_LINE = middle_screen or n_total_lines or 1
    print(
        f'[File: {os.path.abspath(file_name)} ({n_total_lines} lines total after edit)]'
    )
    CURRENT_FILE = file_name
    _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW)
    print(MSG_FILE_UPDATED)

@update_pwd_decorator
def replace_code(
    file_name: str, 
    code_to_replace: str,
    new_code: str
    ) -> None:
    """Replace some lines inside the function 
    (This is used to avoid some potential wrong line numberproblems in edit_file function)

    Args:
        filename: str: The name of the file to create.
        code_to_replace: str: The original code that will be replaced
        new_code: str: new code that will be used
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW

    # Check file
    
    if not _is_valid_filename(file_name):
        
        raise FileNotFoundError('Invalid file name.')

    if not _is_valid_path(file_name):
        
        raise FileNotFoundError('Invalid path or file name.')

    if not _create_paths(file_name):
        
        raise PermissionError('Could not access or create directories.')

    if not os.path.isfile(file_name):
        
        raise FileNotFoundError(f'File {file_name} not found.')

    # Use a temporary file to write changes
    temp_file_path = ''
    src_abs_path = os.path.abspath(file_name)
    first_error_line = None
    try:
        # # lint the original file
        if ENABLE_AUTO_LINT:
            origianl_lint_error, origianl_first_error_line = _lint_file(file_name)      
              
        with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
            temp_file_path = temp_file.name

            # Read the original file and check if empty and for a trailing newline
            with open(file_name) as original_file:
                file_content = original_file.read()   
                def flexible_str(s: str) -> str:
                    s = re.escape(s)
                    flexible_pattern = re.sub(r'\n', r'\n+', s) # change \n to \n\n...\n
                    return flexible_pattern
                
                flexible_code_to_replace = flexible_str(code_to_replace)
                matchs = re.findall(flexible_code_to_replace, file_content)
                occurrences = len(matchs)
                
                # arguments check
                if occurrences == 0:
                    print(
                        f'The code block:\n'
                        f'{code_to_replace}\n'
                        f'is not involved in the {file_name}.\n'
                        'Your changes have NOT been applied.\n'
                        'Please use open_file(path, line_number, context_lines) command to check the details of where you want to modify and fix your command.\n'
                        'Or You can also use the edit_file(file_name, start, start_str end, end_str, content) command to indicate the code block that you want to modify.'
                    )
                    return

                if occurrences > 1:
                    print(
                        f'The code block:\n'
                        f'{code_to_replace}\n'
                        f'is duplicated in the {file_name}.\n'
                        'Your changes have NOT been applied.\n'
                        'Please use the edit_file(file_name, start, start_str end, end_str, content) command to indicate the code block that you want to modify.'
                    )
                    return
                
                # replace the code block
                code_to_replace = matchs[0]
                updated_file_content = file_content.replace(code_to_replace, new_code)
                
            # Write the new content to the temporary file
            temp_file.write(updated_file_content)

        # Replace the original file with the temporary file atomically
        shutil.move(temp_file_path, src_abs_path)
        
        # find the first different line
        original_lines = file_content.splitlines()
        updated_lines = updated_file_content.splitlines()

        for index, (original, updated) in enumerate(zip(original_lines, updated_lines), start=1):
            if original != updated:
                new_code_line = index
                break
                
        # Modified lines
        m_lines = len(new_code.splitlines())
        
        # middle screen
        window = m_lines + 10
        # print(f"window: {window}")
        middle_screen = new_code_line
        # print(f"middle_screen: {middle_screen}")
        
        
        # Handle linting
        if ENABLE_AUTO_LINT:
            # BACKUP the original file
            original_file_backup_path = os.path.join(
                os.path.dirname(file_name),
                f'.backup.{os.path.basename(file_name)}',
            )
            with open(original_file_backup_path, 'w') as f:
                 f.write(file_content)

            lint_error, first_error_line = _lint_file(file_name)

            # Select the errors caused by the modification
            def extract_last_part(line):
                parts = line.split(':')
                if len(parts) > 1:
                    return parts[-1].strip()
                return line.strip()

            def subtract_strings(str1, str2) -> str:
                lines1 = str1.splitlines()
                lines2 = str2.splitlines()
                
                last_parts1 = [extract_last_part(line) for line in lines1]
                
                remaining_lines = [line for line in lines2 if extract_last_part(line) not in last_parts1]

                result = '\n'.join(remaining_lines)
                return result
            if origianl_lint_error:
                if lint_error is not None:
                    lint_error = subtract_strings(origianl_lint_error, lint_error)
                if lint_error == "":
                    lint_error = None
                    first_error_line = None
                                                           
            if lint_error is not None:
                
                if first_error_line is not None:
                    CURRENT_LINE = middle_screen
                print(
                    '[Your proposed edit has introduced new syntax error(s). Please understand the errors and retry your edit command.]'
                )
                
                print('[This is how your edit would have looked if applied]')
                print('-------------------------------------------------')
                _print_window(file_name, CURRENT_LINE, window)
                print('-------------------------------------------------\n')

                print('[This is the original code before your edit]')
                print('-------------------------------------------------')
                _print_window(original_file_backup_path, CURRENT_LINE, window)
                print('-------------------------------------------------')

                print(
                    'Your changes have NOT been applied. Please fix your edit command and try again based on the following error messages.\n'
                    f'{lint_error}\n'
                    'You may need to do one or several of the following:\n'
                    '1) Specify the correct code block that you want to modify;\n' 
                    '2) Make sure that the Args position is correct (the 2nd arg is the origianl code that will be replaced and the 3rd arg is the new code that will be used);\n' 
                    '3) Choose another command (Such as edit_file(file_name, start, start_str end, end_str, content) command).\n'
                    '4) Use open_file(path, line_number, context_lines) command to check the details of where you want to modify and improve your command.\n'
                    'DO NOT re-run the same failed edit command. Running it again will lead to the same error.'
                )

                # recover the original file
                with open(original_file_backup_path) as fin, open(
                    file_name, 'w'
                ) as fout:
                    fout.write(fin.read())
                os.remove(original_file_backup_path)
                return

    except FileNotFoundError as e:
        
        print(f'File not found: {e}')
    except IOError as e:
        
        print(f'An error occurred while handling the file: {e}')
    except ValueError as e:
        
        print(f'Invalid input: {e}')
    except Exception as e:
        
        # Clean up the temporary file if an error occurs
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        print(f'An unexpected error occurred: {e}')
        raise e

    # Update the file information and print the updated content
    with open(file_name, 'r', encoding='utf-8') as file:
        n_total_lines = max(1, len(file.readlines()))
    if first_error_line is not None and int(first_error_line) > 0:
        CURRENT_LINE = first_error_line
    else:
        CURRENT_LINE = middle_screen or n_total_lines or 1
    print(
        f'[File: {os.path.abspath(file_name)} ({n_total_lines} lines total after edit)]'
    )
    CURRENT_FILE = file_name
    _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW)
    print(MSG_FILE_UPDATED)

def _edit_or_append_file(
    file_name: str,
    start: int | None = None,
    start_str: str | None = None,
    end: int | None = None,
    end_str: str| None = None,
    content: str = '',
    is_append: bool = False,
) -> None:
    """Internal method to handle common logic for edit_/append_file methods.

    Args:
        file_name: str: The name of the file to edit or append to.
        start: int | None = None: The start line number for editing. Ignored if is_append is True.
        end: int | None = None: The end line number for editing. Ignored if is_append is True.
        content: str: The content to replace the lines with or to append.
        is_append: bool = False: Whether to append content to the file instead of editing.
    """
    global CURRENT_FILE, CURRENT_LINE, WINDOW
    
    original_file_backup_path = None

    ERROR_MSG = f'[Error editing file {file_name}. Please confirm the file is correct.]'
    ERROR_MSG_SUFFIX = (
        'Your changes have NOT been applied. Please fix your edit command and try again.\n'
        'You either need to 1) Open the correct file and try again or 2) Specify the correct start/end line arguments.\n'
        'DO NOT re-run the same failed edit command. Running it again will lead to the same error.'
    )
    if not _is_valid_filename(file_name):
        
        raise FileNotFoundError('Invalid file name.')

    if not _is_valid_path(file_name):
        
        raise FileNotFoundError('Invalid path or file name.')

    if not _create_paths(file_name):
        
        raise PermissionError('Could not access or create directories.')

    if not os.path.isfile(file_name):
        
        raise FileNotFoundError(f'File {file_name} not found.')

    # Use a temporary file to write changes
    content = str(content or '')
    temp_file_path = ''
    src_abs_path = os.path.abspath(file_name)
    first_error_line = None
    try:
        # # lint the origianl file
        if ENABLE_AUTO_LINT:
            origianl_lint_error, origianl_first_error_line = _lint_file(file_name)
        # Create a temporary file
        with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
            temp_file_path = temp_file.name
            # Read the original file and check if empty and for a trailing newline
            with open(file_name) as original_file:
                lines = original_file.readlines()

            if is_append:
                content_lines = content.splitlines(keepends=True)
                if not start:
                    start = len(lines)
                if lines and not (len(lines) == 1 and lines[0].strip() == ''):
                    if not lines[-1].endswith('\n'):
                        lines[-1] += '\n'
                    if content_lines and not content_lines[-1].endswith('\n'):
                        content_lines[-1] += '\n'
                    new_lines = lines[:start-1] + content_lines + lines[start-1:]
                    content = ''.join(new_lines)
            else:
                # Handle cases where start or end are None
                if start is None:
                    start = 1  # Default to the beginning
                if end is None:
                    end = len(lines)  # Default to the end
                            
                # Check arguments
                if not (1 <= start <= len(lines)):
                    
                    print(
                        f'{ERROR_MSG}\n'
                        f'Invalid start line number: {start}. Line numbers must be between 1 and {len(lines)} (inclusive).\n'
                        f'{ERROR_MSG_SUFFIX}'
                    )
                    return
                if not (1 <= end <= len(lines)):
                    
                    print(
                        f'{ERROR_MSG}\n'
                        f'Invalid end line number: {end}. Line numbers must be between 1 and {len(lines)} (inclusive).\n'
                        f'{ERROR_MSG_SUFFIX}'
                    )
                    return
                if start > end:
                    
                    print(
                        f'{ERROR_MSG}\n'
                        f'Invalid line range: {start}-{end}. Start must be less than or equal to end.\n'
                        f'{ERROR_MSG_SUFFIX}'
                    )
                    return
                
                # Double check if the start/end line is correct by compare with the start_str/end_str
                check_pass = True
                if lines[start-1].replace('\n','') != start_str:
                    print(f'The string: {start_str} does not match the start line: {start}')
                    # print(f'The start line: {start} is {lines[start-1]}')
                    check_pass = False
                if lines[end-1].replace('\n','') != end_str:
                    print(f'The string: {end_str} does not match the end line: {end}')    
                    # print(f'The end line: {end} is {lines[end-1]}')   
                    check_pass = False    
                if check_pass != True:
                    print("Here is the code that you are trying to modified:")
                    window_size = (end - start) + 5
                    target_line = (end + start) // 2
                    start_str_closest_index = match_str(start_str, lines, start)
                    end_str_closest_index = match_str(end_str, lines, end)
                    _print_window(file_name, target_line, window_size)
                    print(
                        f'The start line: {start} is:\n'
                        f'{start}|{lines[start-1]}\n'
                        f'The end line: {end} is:\n'
                        f'{end}|{lines[end-1]}\n'
                    )
                    if start_str_closest_index is not None:
                        print(
                            f"The matching string closest to the line {start} and most similar to the start_str you provided is at position {start_str_closest_index + 1}.\n"
                            f'{start_str_closest_index + 1}|{lines[start_str_closest_index]}'
                        )
                    if end_str_closest_index is not None:
                        print(
                            f"The matching string closest to the line {end} and most similar to the end_str you provided is at position {end_str_closest_index + 1}.\n"
                            f'{end_str_closest_index + 1}|{lines[end_str_closest_index]}'
                        )                    
                    print(
                        'Your changes have NOT been applied. Please fix your edit command and try again.\n'
                        'Please double-check whether this part of the code is what you originally planned to modify\n'
                        "If you want to use the edit_file() command, please provide the correct start line and end line along with the corresponding strings on those lines. And don't forget to provide the `content` argument.\n"
                        "You should first try to use the information above to modify your edit_file() command.\n"
                        'However, if you have already tried to fix this edit_file() command multiple times and the same issue persists, please try using replace_content() to modify the file.'
                    )
                    return

                if not content.endswith('\n'):
                    content += '\n'
                content_lines = content.splitlines(True)
                new_lines = lines[: start - 1] + content_lines + lines[end:]
                content = ''.join(new_lines)

            if not content.endswith('\n'):
                content += '\n'

            # Write the new content to the temporary file
            temp_file.write(content)

        # Replace the original file with the temporary file atomically
        shutil.move(temp_file_path, src_abs_path)

        # Handle linting
        if ENABLE_AUTO_LINT:
            # BACKUP the original file
            original_file_backup_path = os.path.join(
                os.path.dirname(file_name),
                f'.backup.{os.path.basename(file_name)}',
            )
            with open(original_file_backup_path, 'w') as f:
                f.writelines(lines)

            lint_error, first_error_line = _lint_file(file_name)
            
            # Select the errors caused by the modification
            
            def extract_last_part(line):
                parts = line.split(':')
                if len(parts) > 1:
                    return parts[-1].strip()
                return line.strip()

            def subtract_strings(str1, str2) -> str:
                lines1 = str1.splitlines()
                lines2 = str2.splitlines()
                
                last_parts1 = [extract_last_part(line) for line in lines1]
                
                remaining_lines = [line for line in lines2 if extract_last_part(line) not in last_parts1]

                result = '\n'.join(remaining_lines)
                return result
            if origianl_lint_error:
                if lint_error is not None:
                    lint_error = subtract_strings(origianl_lint_error, lint_error)
                if lint_error == "":
                    lint_error = None
                    first_error_line = None
                            
            if lint_error is not None:
                
                if first_error_line is not None:
                    # CURRENT_LINE = int(first_error_line)
                    total_lines = len(content_lines)
                    CURRENT_LINE = int(start) + total_lines // 2 # Try the edited line
                print(
                    '[Your proposed edit has introduced new syntax error(s). Please understand the errors and retry your edit command.]'
                )
                
                print('[This is how your edit would have looked if applied]')
                print('-------------------------------------------------')
                _print_window(file_name, CURRENT_LINE, total_lines + 10)
                print('-------------------------------------------------\n')

                print('[This is the original code before your edit]')
                print('-------------------------------------------------')
                _print_window(original_file_backup_path, CURRENT_LINE, total_lines + 10)
                print('-------------------------------------------------')

                print(
                    'Your changes have NOT been applied. Please fix your edit command and try again based on the following error messages.\n'
                    f'{lint_error}\n'
                    'You probably need to do one or several of the following:\n'
                    '1) Specify the correct start/end line parameters;\n' 
                    '2) Correct your edit code;\n' 
                    '3) Choose another command (Such as replace_function(file_name,code_to_replace,new_code) command).\n'
                    '4) Use open_file(path, line_number, context_lines) command to check the details of where you want to modify and improve your command\n'
                    'DO NOT re-run the same failed edit command. Running it again will lead to the same error.\n'
                    'Do NOT use the bash command to modify the file, as it may lead to unexpected errors.'
                )

                # recover the original file
                with open(original_file_backup_path) as fin, open(
                    file_name, 'w'
                ) as fout:
                    fout.write(fin.read())
                os.remove(original_file_backup_path)
                return
            if os.path.exists(original_file_backup_path):
                os.remove(original_file_backup_path)

    except FileNotFoundError as e:
        
        print(f'File not found: {e}')
    except IOError as e:
        
        print(f'An error occurred while handling the file: {e}')
    except ValueError as e:
        
        print(f'Invalid input: {e}')
    except Exception as e:
        
        # Clean up the temporary file if an error occurs
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        print(f'An unexpected error occurred: {e}')
        raise e
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        if original_file_backup_path and os.path.exists(original_file_backup_path):
            try:
                os.remove(original_file_backup_path)
            except OSError:
                pass
            
    # Update the file information and print the updated content
    with open(file_name, 'r', encoding='utf-8') as file:
        n_total_lines = max(1, len(file.readlines()))
    if first_error_line is not None and int(first_error_line) > 0:
        CURRENT_LINE = first_error_line
    else:
        if is_append:
            # CURRENT_LINE = max(1, len(lines))  # end of original file
            total_lines = len(content_lines)
            CURRENT_LINE = (total_lines) // 2 + start
            WINDOW = total_lines + 10
        else:
            CURRENT_LINE = start or n_total_lines or 1
    print(
        f'[File: {os.path.abspath(file_name)} ({n_total_lines} lines total after edit)]'
    )
    CURRENT_FILE = file_name
    _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW)
    print(MSG_FILE_UPDATED)
    

@update_pwd_decorator
def edit_file(file_name: str, start_line: int, start_str: str, end_line: int, end_str: str, content: str) -> None:
    """Edit a file.

    Replaces in given file `file_name` the lines `start` through `end` (inclusive) with the given text `content`.
    If a line must be inserted, an already existing line must be passed in `content` with new content accordingly!
    The parameters start_str and end_str will be used to verify if the lines you specified are correct. 
    start_str should correspond to the string on the start line, and end_str should correspond to the string on the end line.
    To avoid potential errors, the string corresponding to content should first be assigned to a variable, and then that variable should be used in the command.
    
    For example:
    EDIT_CODE = '''
    <CONTENT>
    '''
    edit_file(file_name, start, start_str, end, end_str, content=EDIT_CODE)
    
    Args:
        file_name: str: The name of the file to edit.
        start: int: The start line number. Must satisfy start >= 1.
        start_str: str: String on the start line.
        end: int: The end line number. Must satisfy start <= end <= number of lines in the file.
        end_str: str: String on the end line.
        content: str: The content to replace the lines with.
    """
    _edit_or_append_file(
        file_name, start=start_line, start_str=start_str, end=end_line, end_str=end_str, content=content, is_append=False
    )

@update_pwd_decorator
def append_file(file_name: str, content: str, start_line: int | None = None) -> None:
    """Append content to the given file.

    It appends text `content` to the end of the specified file.

    Args:
        file_name: str: The name of the file to append to.
        content: str: The content to append to the file.
    """
    _edit_or_append_file(file_name, start=start_line, end=None, content=content, is_append=True)

@update_pwd_decorator
def replace_content(file_name: str, old_content: str, new_content: str | None = None) -> None:
    """
    Replace content in a file.
    """
    # -------- 参数校验 --------
    if not _is_valid_filename(file_name):
        raise FileNotFoundError('Invalid file name.')
    if not _is_valid_path(file_name):
        raise FileNotFoundError('Invalid path or file name.')
    if not _create_paths(file_name):
        raise PermissionError('Could not access or create directories.')
    if not os.path.isfile(file_name):
        raise FileNotFoundError(f'File {file_name} not found.')

    # -------- 读取原始内容 --------
    with open(file_name, 'r', encoding='utf-8') as f:
        file_content = f.read().expandtabs()

    old_content = old_content.expandtabs()
    new_content = (new_content or "").expandtabs()

    occurrences = file_content.count(old_content)
    if occurrences == 0:
        raise Exception(
            f"No replacement was performed, old_content `{old_content}` did not appear verbatim in {file_name}. "
            "Please ensure it appears exactly once.\n"
            "If the issue presists, please use edit_file() function to modify the file."
        )
    if occurrences > 1:
        # 计算所有出现位置对应的行号，提示用户
        starts, pos = [], 0
        while True:
            idx = file_content.find(old_content, pos)
            if idx == -1:
                break
            starts.append(idx)
            pos = idx + 1

        line_offsets = [0]
        for line in file_content.split("\n"):
            line_offsets.append(line_offsets[-1] + len(line) + 1)

        def byte_to_line(off: int) -> int:
            for i in range(len(line_offsets) - 1):
                if line_offsets[i] <= off < line_offsets[i + 1]:
                    return i + 1
            return len(line_offsets) - 1

        lines = sorted({byte_to_line(idx) for idx in starts})
        raise Exception(
            f"No replacement was performed. Multiple occurrences of old_content `{old_content}` "
            f"in lines {lines}. Please ensure it appears exactly once"
            "If the issue presists, please use edit_file() function to modify the file."
        )

    # -------- 记录替换范围行号（用于打印）--------
    start_idx = file_content.find(old_content)
    end_idx = start_idx + len(old_content)

    line_offsets = [0]
    for line in file_content.split("\n"):
        line_offsets.append(line_offsets[-1] + len(line) + 1)

    def byte_to_line(off: int) -> int:
        for i in range(len(line_offsets) - 1):
            if line_offsets[i] <= off < line_offsets[i + 1]:
                return i + 1
        return len(line_offsets) - 1

    start_line = byte_to_line(start_idx)
    end_line   = byte_to_line(end_idx - 1)

    # -------- 自动 lint 及回滚逻辑 --------
    temp_backup_path = None
    try:
        # 先记录原始 lint 错误（若开启）
        if ENABLE_AUTO_LINT:
            orig_lint_err, _ = _lint_file(file_name)

        # 1. 备份原文件
        temp_backup_path = os.path.join(
            os.path.dirname(file_name),
            f'.backup.{os.path.basename(file_name)}',
        )
        shutil.copy2(file_name, temp_backup_path)

        # 2. 执行替换并写回
        new_file_content = file_content.replace(old_content, new_content)
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(new_file_content)

        # 3. lint 检查
        if ENABLE_AUTO_LINT:
            lint_err, first_err_line = _lint_file(file_name)

            # 过滤掉原本就存在的错误，保留新引入的
            def _extract_last_part(line: str) -> str:
                parts = line.split(':')
                return parts[-1].strip() if len(parts) > 1 else line.strip()

            if orig_lint_err:
                orig_set = {_extract_last_part(l) for l in orig_lint_err.splitlines()}
                new_err_lines = [
                    l for l in (lint_err.splitlines() if lint_err else [])
                    if _extract_last_part(l) not in orig_set
                ]
                lint_err = "\n".join(new_err_lines) or None
                first_err_line = first_err_line if new_err_lines else None

            # 若引入了新错误 → 回滚并报错
            if lint_err:
                with open(temp_backup_path, 'r', encoding='utf-8') as fin, \
                     open(file_name, 'w', encoding='utf-8') as fout:
                    fout.write(fin.read())          # 回滚

                print('[Your proposed replace_content() introduced new syntax error(s).]')  # 用户提示
                print(lint_err)
                raise Exception('Replacement aborted due to new lint errors. Please fix them first.')

        # 4. lint 通过 → 删除备份
        if temp_backup_path and os.path.exists(temp_backup_path):
            os.remove(temp_backup_path)

    finally:
        # 保底清理：若函数异常退出也不残留备份
        if temp_backup_path and os.path.exists(temp_backup_path):
            try:
                os.remove(temp_backup_path)
            except OSError:
                pass

    # -------- 打印成功窗口 --------
    middle_line = (start_line + end_line) // 2
    window      = end_line - start_line + 10

    with open(file_name, 'r', encoding='utf-8') as f:
        n_total_lines = max(1, len(f.readlines()))

    print(f'[File: {os.path.abspath(file_name)} ({n_total_lines} lines total after edit)]')
    global CURRENT_FILE, CURRENT_LINE, WINDOW
    CURRENT_FILE = file_name
    CURRENT_LINE = middle_line
    WINDOW       = window
    _print_window(CURRENT_FILE, CURRENT_LINE, WINDOW)
    print(MSG_FILE_UPDATED)


    