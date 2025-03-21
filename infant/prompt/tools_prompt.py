tool_sys_msg = '''
Please collaborate with me to fulfill a request. For each step, provide the necessary command to execute, and I will return the results.

**Guidelines:**
> You can choose from the following commands:
{tools}
> Only one command can be executed at a time.
> We will break the request into smaller tasks and complete them step by step.
> Once a task is completed, I will ask the user for the next step. You do not need to determine the next task in advance.

**Example:**
{one_shot}

**Instructions for Task Completion:**
> If you think the **current task** is already solved, please say:
<task_finish>
exit
</task_finish>. 
> Othereise, please provide the next command inside the corresponding tag.

Now, Please help me to solve the real request.
'''

tool_code_exe = '''
You can use any Bash commands.
Please put the Bash commands you think need to be executed within <execute_bash>...</execute_bash> tags.
'''

tool_file_edit = '''
You can use the following file editing functions to view, add, delete, search, and modify files.
- open_file(path: str, line_number: int | None = 1, context_lines: int = 100): Opens a file and optionally moves to a specific line.
- goto_line(line_number): Moves the window to show the specified line number.
- scroll_down(): Moves the window down by the number of lines specified in WINDOW.
- scroll_up(): Moves the window up by the number of lines specified in WINDOW.
- create_file(filename): Creates and opens a new file with the given name.
- search_dir(search_term, dir_path='./'): Searches for a term in all files in the specified directory.
- search_file(search_term, file_path=None): Searches for a term in the specified file or the currently open file.
- find_file(file_name, dir_path='./'): Finds all files with the given name in the specified directory.
- edit_file(file_name, start, start_str end, end_str, content): Replaces lines in a file with the given content. The start_str should be present in the start line and end_str should be present in the end line.
- append_file(file_name, content): Appends given content to a file.
- replace_function(file_name,function_to_replace,new_code): Replace the exsiting function: function_to_replace inside the file: file_name.
- search_function(file_path, function_signature): Search and show a function in the file. For the function_signature, you should only input the function name.
Please put the file editing commands you think need to be executed within <execute_ipython>...</execute_ipython> tags.
'''

tool_file_edit_one_shot = '''
Here is an example:
USER:
Please create a table in the file "app.py" and display the numbers from 1 to 10 in it.

ASSISTANT: Please help me break the user's request into smaller tasks, and I will complete them one by one.

USER:
Current Task: Let's first create a list of numbers from 1 to 10, and display them in a web page at port 5000.

ASSISTANT:
Sure! Let me create a Python file `app.py`:
<execute_ipython>
create_file('app.py')
</execute_ipython>

USER:
OBSERVATION:
[File: /workspace/app.py (1 lines total)]
1|
[File app.py created.]

ASSISTANT:
Now I will write the Python code for starting a web server and save it to the file `app.py`:
<execute_ipython>
EDITED_CODE=\"\"\"from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    numbers = list(range(1, 11))
    return str(numbers)

if __name__ == '__main__':
    app.run(port=5000)\"\"\"
edit_file('app.py', start=1, start_str='', end=1, end_str='', content=EDITED_CODE)
</execute_ipython>

USER:
OBSERVATION:
1|from flask import Flask
2|app = Flask(__name__)
3|
4|@app.route('/')
5|def index():
6|    numbers = list(range(1, 11))
7|    return str(numbers)
8|
9|if __name__ == '__main__':
10|    app.run(port=5000)
[File updated. Please review the changes and make sure they are correct (correct indentation, no duplicate lines, etc). Edit the file again if necessary.]

ASSISTANT:
I have created a Python file `app.py` that will display a list of numbers from 1 to 10 when you run it. Let me run the Python file for you:
<execute_bash>
python3 app.py > server.log 2>&1 &
</execute_bash>

USER:
OBSERVATION:
[1] 121[1]+  Exit 1                  python3 app.py > server.log 2>&1

ASSISTANT: Looks like the server is running with PID 121 then crashed. Let me check the server log:
<execute_bash>
cat server.log
</execute_bash>

USER:
OBSERVATION:
Traceback (most recent call last):
  File "/workspace/app.py", line 2, in <module>
    from flask import Flask
ModuleNotFoundError: No module named 'flask'

ASSISTANT:
It seems that Flask is not installed. Let me install Flask for you:
<execute_bash>
pip install flask
</execute_bash>

USER:
OBSERVATION:
Defaulting to user installation because normal site-packages is not writeable
Collecting flask
  Using cached flask-3.0.3-py3-none-any.whl (101 kB)
Collecting blinker>=1.6.2
  Using cached blinker-1.7.0-py3-none-any.whl (13 kB)
Collecting Werkzeug>=3.0.0
  Using cached werkzeug-3.0.2-py3-none-any.whl (226 kB)
Collecting click>=8.1.3
  Using cached click-8.1.7-py3-none-any.whl (97 kB)
Collecting itsdangerous>=2.1.2
  Using cached itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Requirement already satisfied: Jinja2>=3.1.2 in /home/user/.local/lib/python3.10/site-packages (from flask) (3.1.3)
Requirement already satisfied: MarkupSafe>=2.0 in /home/user/.local/lib/python3.10/site-packages (from Jinja2>=3.1.2->flask) (2.1.5)
Installing collected packages: Werkzeug, itsdangerous, click, blinker, flask
Successfully installed Werkzeug-3.0.2 blinker-1.7.0 click-8.1.7 flask-3.0.3 itsdangerous-2.2.0

ASSISTANT:
Now that Flask is installed, let me run the Python file again:
<execute_bash>
python3 app.py > server.log 2>&1 &
</execute_bash>

USER:
OBSERVATION:
[1] 124

ASSISTANT:
Let me check the server log again:
<execute_bash>
cat server.log
</execute_bash>

USER:
OBSERVATION:
* Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit

ASSISTANT:
The server is running on port 5000 with PID 124. You can access the list of numbers by visiting http://127.0.0.1:5000. If you have any further questions, feel free to ask!

USER: Now browse the newly started server's homepage and show me the content.

ASSISTANT:
Sure! Let me browse the server's homepage at http://127.0.0.1:5000:
<execute_browse>
Get the content on "http://127.0.0.1:5000"
</execute_browse>

USER:
OBSERVATION:
[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

ASSISTANT:
The content of the server's homepage is "[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]". If you have any further questions, feel free to ask!

USER: Now kill the server, make it display the numbers in a table format.

ASSISTANT:
Sure! Let me stop the server first:
<execute_bash>
kill 124
</execute_bash>

USER:
OBSERVATION:
[1]+  Terminated              python3 app.py > server.log 2>&1

ASSISTANT:
The server has been stopped. Let me open the Python file and modify it.
<execute_ipython>
open_file('app.py')
</execute_ipython>

USER:
[File: /workspace/app.py (10 lines total)]
1|from flask import Flask
2|app = Flask(__name__)
3|
4|@app.route('/')
5|def index():
6|    numbers = list(range(1, 11))
7|    return str(numbers)
8|
9|if __name__ == '__main__':
10|    app.run(port=5000)

ASSISTANT:
I should edit the file to display the numbers in a table format. I should include correct indentation. Let me update the file:
<execute_ipython>
edit_file('app.py', start=7, start_str='    return str(numbers)', end=7, end_str='    return str(numbers)', content="    return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'")
</execute_ipython>

USER:
Observation:
[File: /workspace/app.py (10 lines total after edit)]
1|from flask import Flask
2|app = Flask(__name__)
3|
4|@app.route('/')
5|def index():
6|    numbers = list(range(1, 11))
7|    return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'
8|
9|if __name__ == '__main__':
10|    app.run(port=5000)
[File updated. Please review the changes and make sure they are correct (correct indentation, no duplicate lines, etc). Edit the file again if necessary.]

ASSISTANT:
Running the updated file:
<execute_bash>
python3 app.py > server.log 2>&1 &
</execute_bash>

USER:
Observation:
[1] 126

ASSISTANT:
The server is running on port 5000 with PID 126. You can access the list of numbers in a table format by visiting http://127.0.0.1:5000. 
The current task is complete. If you have any further questions, feel free to ask!
<task_finish>
exit
</task_finish>
'''

tool_web_browse = '''
You can use the following functions to interact with the browser.
- open_browser(): Open the browser in headless mode.
- navigate_to(url: str) : Navigate to the specified URL.
- refresh_page(): Refresh the current page.
- go_back(): Go back to the previous page.
- go_forward(): Go forward to the next page.
- close_current_tab(): Close the current tab.
- execute_javascript(script: str): Execute the specified JavaScript code.
- switch_to_tab(page_id: int): Switch to the tab at the specified index.
- create_new_tab(url: str): Open a new tab with the specified URL.
- save_cookies(): Save the current cookies.
- select_dropdown_option(index: int, option: int): Select the specified option from the dropdown menu. index: selector index. option: Index of the option to select.
- mouse_left_click(item: str, description: str): Left mouse click at the specified position. For example: mouse_left_click('search bar', 'It is located near the top center of the Google Chrome browser window. It is a long, rectangular input field with rounded edges. The search bar spans almost the entire width of the browser window and sits directly below the browser's tab row. It has placeholder text that reads "Search Google or type a URL." The search bar is centrally aligned, making it easy to spot above the main content area of the browser.')
- mouse_double_click(item: str, description: str): Double-click at the specified position. For example: mouse_double_click('The VSCode icon', 'It is located in the sidebar (Launcher) on the left side of the screen. It is the first icon from the top in the vertical arrangement. The icon has a blue background with a white folded "V"-shaped design in the center. The sidebar is aligned along the leftmost edge of the screen, adjacent to the desktop background on its right side.')
- mouse_right_click(item: str, description: str): Right mouse click at the specified position. For example: mouse_right_click('The refresh button', 'It is located at the top-left corner of the Google Chrome browser window, inside the address bar. It is a circular arrow icon situated next to the left and right navigation arrows (back and forward buttons). The refresh button is just to the left of the search bar. Click it to refresh the current page.')
- type_text(text: str): Type the given text. text: The text to type.
- press_key(key: str): Presses the specified key. key: The key or key combination to press (e.g., "Return", "Ctrl+c").
- press_key_combination(keys: List[str]): Presses the specified key combination.
- mouse_drag(x_start: int, y_start: int, x_end: int, y_end: int): Drag the mouse from one position to another. x_start: Starting x-coordinate. y_start: Starting y-coordinate. x_end: Ending x-coordinate. y_end: Ending y-coordinate.
- mouse_box_select(x_start: int, y_start: int, x_end: int, y_end: int): Selects a box by dragging the mouse from one position to another. x_start: Starting x-coordinate. y_start: Starting y-coordinate. x_end: Ending x-coordinate. y_end: Ending y-coordinate.
- close(): Close the browser.
'''

tool_web_browse_one_shot = '''
Here is an example:
Current Task: Open Wikipedia and search for "Artificial Intelligence".
Assistant: 
Open the chrome.
<execute_ipython>
open_browser()
</execute_ipython>

User:
Screenshot of the chrome opened.

Assistant: 
Open a new tab in the browser and navigate to Wikipedia.
<execute_ipython>
create_new_tab("https://www.wikipedia.org/")
</execute_ipython>

User:
Screenshot of the Wikipedia homepage opened.
All DOMElementNodes have been highlighted and numbered in the screenshot.

Assistant:
Click on the search bar.
<execute_ipython>
mouse_left_click(item='search bar', description='It is located near the top center of the Wikipedia homepage. It is a rectangular input field with placeholder text "Search Wikipedia".')
</execute_ipython>

User:
Screenshot of the search bar clicked.
All DOMElementNodes have been highlighted and numbered in the screenshot.

Assistant:
Type "Artificial Intelligence" in the search bar.
<execute_ipython>
type_text("Artificial Intelligence")
</execute_ipython>

User:
Screenshot of the search term "Artificial Intelligence" entered.
All DOMElementNodes have been highlighted and numbered in the screenshot.

Assistant:
Press the "Enter" key to perform the search.
<execute_ipython>
press_key("Return")
</execute_ipython>

User:
Screenshot of the Wikipedia search results for "Artificial Intelligence".

Assistant:
Click on the first search result.
<execute_ipython>
mouse_left_click(item='the first search result', description='It is located near the top right of the homepage.')
</execute_ipython>

User:
Screenshot of the Wikipedia page for "Artificial Intelligence".

Assistant:
The task is complete. You can now view the Wikipedia page for "Artificial Intelligence".

<task_finish>exit</task_finish>
'''

tool_web_browse_note = '''**NOTE:**
When using a browser, if a dropdown menu appears, you need to first select the correct option from the menu before proceeding with the next steps. If the dropdown menu does not contain the content you need, click on any blank area to dismiss it.
'''


tool_mk_operation = '''
You can use the following functions to perform various mouse and keyboard operations.
- take_screenshot(): If you want to check the current screen, you can use this command to take a screenshot of the current screen.
- mouse_left_click(item: str, description: str): Left mouse click at the specified position. For example: mouse_left_click('search bar', 'It is located near the top center of the Google Chrome browser window. It is a long, rectangular input field with rounded edges. The search bar spans almost the entire width of the browser window and sits directly below the browser's tab row. It has placeholder text that reads "Search Google or type a URL." The search bar is centrally aligned, making it easy to spot above the main content area of the browser.')
- mouse_double_click(item: str, description: str): Double-click at the specified position. For example: mouse_double_click('The VSCode icon', 'It is located in the sidebar (Launcher) on the left side of the screen. It is the first icon from the top in the vertical arrangement. The icon has a blue background with a white folded "V"-shaped design in the center. The sidebar is aligned along the leftmost edge of the screen, adjacent to the desktop background on its right side.')
- mouse_right_click(item: str, description: str): Right mouse click at the specified position. For example: mouse_right_click('The refresh button', 'It is located at the top-left corner of the Google Chrome browser window, inside the address bar. It is a circular arrow icon situated next to the left and right navigation arrows (back and forward buttons). The refresh button is just to the left of the search bar. Click it to refresh the current page.')
- mouse_scroll(direction: str, amount: int): Scroll mouse scroll up or down. direction: Direction to scroll ("up" or "down"). amount: Number of times to scroll.
- type_text(text: str): Type the given text. text: The text to type.
- press_key(key: str): Presses the specified key. key: The key or key combination to press (e.g., "Return", "Ctrl+c").
- open_application(app_name: str): Opens a specific application using the system application launcher. app_name: The name of the application to open (e.g., "chrome").
- press_key_combination(keys: List[str]): Presses the specified key combination.
- mouse_drag(x_start: int, y_start: int, x_end: int, y_end: int): Drag the mouse from one position to another. x_start: Starting x-coordinate. y_start: Starting y-coordinate. x_end: Ending x-coordinate. y_end: Ending y-coordinate.
- mouse_box_select(x_start: int, y_start: int, x_end: int, y_end: int): Selects a box by dragging the mouse from one position to another. x_start: Starting x-coordinate. y_start: Starting y-coordinate. x_end: Ending x-coordinate. y_end: Ending y-coordinate.
Please put the mouse/keyboard operations you think need to be executed inside the <execute_ipython>...</execute_ipython> tags.
'''

tool_mk_one_shot = '''
Here is an example:
Current Task: Search a picture of kittens from Google.

Assistant: 
Open the Chrome browser.
<execute_ipython>
open_application("chrome")
</execute_ipython>

User:
Screenshot of the Chrome browser opened on the screen.

Assistant:
Click on the search bar.
<execute_ipython>
mouse_left_click(item='search bar', description='It is located near the top center of the Google Chrome browser window.')
</execute_ipython>

User:
Screenshot of the search bar clicked.

Assistant:
Type "kittens" in the search bar.
<execute_ipython>
type_text("kittens")
</execute_ipython>

User:
Screenshot of the search term "kittens" entered.

Assistant:
Let's double check the current screen.  
<execute_ipython>
take_screenshot()
</execute_ipython>

User:
Screenshot of the current screen.

Assistant:
It seems that the search term is correct.
Press the "Enter" key to perform the search.
<execute_ipython>
press_key("Return")
</execute_ipython>

User:
Screenshot of the search results for "kittens".

Assistant:
The task is complete. You can now view the search results for "kittens".

<task_finish>exit</task_finish>
'''


tool_fake_user_response_prompt = '''You did not provide any commands. If you believe the task is complete or cannot be solved, reply with <task_finish>exit</task_finish>; otherwise, please provide a command.'''

tool_document = {
    "code_exec": tool_code_exe,
    "file_edit": tool_file_edit,
    "web_browse": tool_web_browse,
    "computer_interaction": tool_mk_operation
}

tool_example = {
    "code_exec": '',
    "file_edit": tool_file_edit_one_shot,
    "web_browse": tool_web_browse_one_shot,
    "computer_interaction": tool_mk_one_shot
}

tool_stop = {
    "code_exec": '</execute_bash>',
    "file_edit": '</execute_ipython>',
    "web_browse": '</execute_ipython>',
    "computer_interaction": '</execute_ipython>'
}

tool_note = {
    "code_exec": '',
    "file_edit": '',
    "web_browse": tool_web_browse_note,
    "computer_interaction": ''
}

tool_trace_code = '''import sys
import os
import re
import inspect

def find_workspace_root(current_path):
while True:
    parent_path = os.path.dirname(current_path)  
    if parent_path == '/workspace':  
        return current_path  
    elif parent_path == current_path: 
        raise FileNotFoundError("Workspace root not found.")
    current_path = parent_path

WORKSPACE_PATH = find_workspace_root(os.path.abspath(__file__))
print(f"WORKSPACE_PATH:{WORKSPACE_PATH}")
TRACE_FILE_PATH = os.path.abspath(__file__)

printed_traces = []

def trace_calls(frame, event, arg):
def format_arguments(frame):
    args = inspect.getargvalues(frame)
    arg_values = args.locals
    formatted_args = []
    for k in args.args:
        if k == "self":
            formatted_args.append("self")
        else:
            formatted_args.append(f"{k}={arg_values[k]}")
    return ", ".join(formatted_args)

if event == "call":
    code = frame.f_code
    func_name = code.co_name
    filename = os.path.abspath(code.co_filename)
    lineno = frame.f_lineno
    if filename == TRACE_FILE_PATH:
        lineno -= 54
            
    if WORKSPACE_PATH in filename and not re.search(r'<[^>]*>', filename):
        # filename = filename.replace(WORKSPACE_PATH, '')
        if 'self' in frame.f_locals:
            class_name = frame.f_locals['self'].__class__.__name__
            trace_info = f'{class_name}.{func_name}() in {filename} at line {lineno}'
        else:
            trace_info = f'{func_name}() in {filename} at line {lineno}'
        
        if not re.search(r'<[^>]*>', trace_info):
            print(trace_info)
return trace_calls

sys.settrace(trace_calls)

'''

tool_filter_bash_code = '''#!/bin/bash

txt_file="/tmp/temp.txt"
temp_file="/tmp/filtered.txt"

at_line=" at line "

> $temp_file

while IFS= read -r line; do
if [[ "$line" != *"$at_line"* ]]; then
    line_number=$(grep -Fn "$line" "$txt_file" | cut -d: -f1 | head -n 1)
    
    if [[ -z "$line_number" ]]; then
        continue
    fi
    
    sed -n "${line_number},\$p" "$txt_file" >> "$temp_file"
fi
done < "$txt_file"

sort -u "$temp_file" > /tmp/unique_lines.txt

grep -F "$at_line" /tmp/unique_lines.txt > /tmp/final_output.txt

'''