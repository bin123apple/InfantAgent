IMPORTS = '''import sys
from computer_use.computeruse import *
from file_editor.fileeditor import *
from file_searcher.filesearcher import *
from file_reader.filereader import *
from web_browser.browser import *
from advanced_tools.advancedtools import *'''

tool_sys_msg = '''
Please collaborate with me to fulfill a request. For each step, provide the necessary command to execute, and I will return the results.

**Guidelines:**
> You have the capability to execute one of the following commands:
{tools}
> Only one command can be executed at a time. The result of the command will be displayed before proceeding to the next step.
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

tool_file_understand = '''
You can use the following functions to understand the content of files. Such as reading files, view images, listen to audios, watch videos, etc.
- open_file(path: str, line_number: int | None = 1, context_lines: int = 100): Opens a file and optionally moves to a specific line. path: Path to the file. line_number: Line number to move to. context_lines: Number of lines to display.
- parse_pdf(pdf_path: str, page: int): View the specified page of a PDF file. pdf_path: Path to the PDF file. page: Page number to view.
- parse_figure(figure_path: str): View the specified figure. figure_path: Path to the figure file.
- parse_audio(audio_path: str, question: str): Ask a question about the audio file. audio_path: Path to the audio file. question: Question to ask.
- zoom_pdf(pdf_path: str, page: int, region: tuple): Zoom in on a specific region of a PDF file. pdf_path: Path to the PDF file. page: Page number to view. region: Tuple specifying the region to zoom in on (x0, y0, x1, y1).
Please put the file viewing commands you think need to be executed within <execute_ipython>...</execute_ipython> tags.
'''

tool_file_understand_one_shot = '''
Here is an example:
USER:
Please open the file "example.txt" and
show the content starting from line 5.

ASSISTANT:
Sure! Let me open the file "example.txt" and move to line 5:
<execute_ipython>
open_file('example.txt', line_number=5)
</execute_ipython>

USER:
OBSERVATION:
[File: /workspace/example.txt (5 lines total)]
1|This is an example file.
2|It contains some text data.
3|Lorem ipsum dolor sit amet,
4|consectetur adipiscing elit.
5|Sed do eiusmod tempor incididunt

ASSISTANT:
What would you like to do next?

USER:
Please view the example.pdf file and show the content of page 3.

ASSISTANT:
Sure! Let me view page 3 of the PDF file "example.pdf":
<execute_ipython>
parse_pdf('example.pdf', page=3)
</execute_ipython>

USER:
OBSERVATION:
[PDF: example.pdf, Page 3]
[PDF content displayed.]

ASSISTANT:
What would you like to do next?

USER:
Please zoom in on the region (100, 100, 200, 200) of page 3 in the example.pdf file.

ASSISTANT:
Sure! Let me zoom in on the specified region of page 3 in the PDF file "example.pdf":
<execute_ipython>
zoom_pdf('example.pdf', page=3, region=(100, 100, 200, 200))
</execute_ipython>

USER:
OBSERVATION:
[PDF: example.pdf, Page 3, Region (100, 100, 200, 200)]
[Zoomed-in region displayed.]

ASSISTANT:
The current task is complete. If you have any further questions, feel free to ask!
<task_finish>
exit
</task_finish>

USER: 
My friend from class sent me an audio recording of Professor Willowbrook giving out the recommended reading for the test, but my headphones are broken :(\n\nCould you please listen to the recording for me and tell me the page numbers I'm supposed to go over? I've attached a file called Homework.mp3 that has the recording. 

ASSISTANT:
Sure! Let me parse the audio file "Homework.mp3" and ask the question:
<execute_ipython>
parse_audio('Homework.mp3', question='please tell me the review page numbers recommended by Professor Willowbrook for the exam.')
</execute_ipython>

USER:
[Answer from the audio file displayed.]

ASSISTANT:
<task_finish>
exit
</task_finish>
'''


tool_file_edit = '''
You can use the following file editing functions to view, add, delete, search, and modify files.
- create_file(filename): Creates and opens a new file with the given name.
- search_dir(search_term, dir_path='./'): Searches for a term in all files in the specified directory.
- find_file(file_name, dir_path='./'): Finds all files with the given name in the specified directory.
- replace_content(file_path, old_content, new_content): Replaces the old content with the new content in the specified file.
- append_file(file_name, content, start_line): Appends given content to a file. file_name: Name of the file. content: Content to append. start_line: Line number to start appending from (default is the end of the file).
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
append_file('app.py', EDITED_CODE)
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

ASSISTANT: Let's insert a print() statement to confirm the server is running correctly. Then, I will run the Python file to start the server:
<execute_ipython>
append_file('app.py', "print('Server is running on port 5000...')", 10)
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
10|    print('Server is running on port 5000...')
11|    app.run(port=5000)
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
replace_content('app.py', 'return str(numbers)', "return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'")
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
- open_browser(): Open the browser.
- navigate_to(url: str) : Navigate to the specified URL.
- refresh_page(): Refresh the current page.
- get_page_html(): get the HTML code of the current page.
- go_back(): Go back to the previous page.
- go_forward(): Go forward to the next page.
- clear_text(): Clear the text in the current input field. please make sure the input field is selected before using this command.
- close_current_tab(): Close the current tab.
- execute_javascript(script: str): Execute the specified JavaScript code.
- switch_to_tab(page_id: int): Switch to the tab at the specified index.
- create_new_tab(url: str): Open a new tab with the specified URL.
- save_cookies(): Save the current cookies.
- download(url: str, save_dir: str): If you know the url of the file, you can use this command to download the file from the specified URL to the specified directory.
- select_dropdown_option(selector_index: int, option: int): Select the specified option from the dropdown menu. selector_index: selector index. option: Index of the option to select.
- google_search(content: str): Perform a Google search for the specified content. content: The content to search for.
- close(): Close the browser.
'''

tool_web_browse_one_shot = '''
Here is an example:
Current Task: Open Wikipedia and search for "Artificial Intelligence regulation".
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
Let's go back to the Wikipedia homepage and search for "Artificial Intelligence regulation".
<execute_ipython>
go_back()
</execute_ipython>

User:
Screenshot of the Wikipedia homepage.

Assistant:
Click on the search bar again.
<execute_ipython>
mouse_left_click(item='search bar', description='It is located near the top center of the Wikipedia homepage. It is a rectangular input field with placeholder text "Search Wikipedia".')
</execute_ipython>

User:
Screenshot of the search bar clicked.

Assistant:
Clear the text in the search bar.
<execute_ipython>
clear_text()
</execute_ipython>

User:
Screenshot of the search bar cleared.

Assistant:
Type "Artificial Intelligence regulation" in the search bar.
<execute_ipython>
type_text("Artificial Intelligence regulation")
</execute_ipython>

User:
Screenshot of the search term "Artificial Intelligence regulation" entered.
All DOMElementNodes have been highlighted and numbered in the screenshot.

Assistant:
Click on the first search result.
<execute_ipython>
mouse_left_click(item='the first search result', description='It is located near the top right of the homepage.')
</execute_ipython>

User:
Screenshot of the Wikipedia page for "Artificial Intelligence regulation".

Assistant:
The task is complete. You can now view the Wikipedia page for "Artificial Intelligence regulation".

<task_finish>exit</task_finish>

USER:
Search for today's news on Google.

Assistant:
Sure! Let me open the Chrome browser.
<execute_ipython>
open_browser()
</execute_ipython>

USER:
[Screenshot of the Chrome browser opened.]

Assistant:
Let me search for today's news on Google:
<execute_ipython>
google_search("today's news")
</execute_ipython>

USER:
[Screenshot of the search results displayed.]

Assistant:
The task is complete. You can now view today's news on Google.
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
- mouse_drag(x_start: int, y_start: int, x_end: int, y_end: int): Drag the mouse from one position to another. x_start: Starting x-coordinate. y_start: Starting y-coordinate. x_end: Ending x-coordinate. y_end: Ending y-coordinate.
- mouse_box_select(x_start: int, y_start: int, x_end: int, y_end: int): Selects a box by dragging the mouse from one position to another. x_start: Starting x-coordinate. y_start: Starting y-coordinate. x_end: Ending x-coordinate. y_end: Ending y-coordinate.
Please put the mouse/keyboard operations you think need to be executed inside the <execute_ipython>...</execute_ipython> tags.
'''

tool_mk_one_shot = '''
Here is an example:
Current Task: Search a picture of kittens from Google and save to desktop.

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
Let's save our modifications to local computer.
<execute_ipython>
press_key("Ctrl+s")
</execute_ipython>

User:
Screenshot of the save picture.

Assistant:
The task is complete. You can now view the picture for "kittens" at your local computer.

<task_finish>exit</task_finish>
'''

tool_advanced = '''
You can use the following functions to perform advanced operations. These commands are compound commands. When available, please prefer using these commands rather than attempting to perform the operations by yourself.
- search_arxiv(keyword: str, start_date: str, end_date: str, subject: str, field: str) : Searches for papers on arXiv based on the given keyword, date range, subject (options: cs, math, physics, q-bio, q-fin, stat), and keyword field (options: title, abstract, comments, author, all). Returns the search results.
- download_arxiv_pdf(arxiv_id: str) : Downloads the specified arXiv paper based on its ID (eg: 1608.06816) and show the first page of the PDF.
- scroll_pdf_page(direction: str, pages: int): When you're viewing a PDF document in the web interface, you can use this command to scroll the specified page of the PDF file up or down. direction: Direction to scroll ("up" or "down"). page: Page number to scroll.
- watch_video(video_path_or_url: str): Watch a video file or YouTube URL. video_path_or_url: Local path or YouTube URL.
'''

tool_advanced_one_shot = '''
Here is an example:
USER:
Search for papers on arXiv related to "Artificial Intelligence" from 2022-01-01 to 2023-01-01.

Assistant:
Sure! Let me search for papers on arXiv related to "Artificial Intelligence" from 2022-01-01 to 2023-01-01:
<execute_ipython>
search_arxiv("Artificial Intelligence", "2022-01-01", "2023-01-01", subject="cs", field="title")
</execute_ipython>

USER:
OBSERVATION:
[1] 
arXiv ID: 12345678
Title: "A Comprehensive Survey on Artificial Intelligence"  
Authors: John Doe, Jane Smith
[2] 
arXiv ID: 23456789
Title: "Advancements in AI Technology"
Authors: Alice Johnson, Bob Brown
[3] 
arXiv ID: 34567890
Title: "AI in Healthcare: A Review"
Authors: Charlie Green, David Blue

Assistant:
Great! I found some papers related to "Artificial Intelligence".
Please let me know if you want to download any of them.

USER:
Please download the paper with ID 12345678.

Assistant:
Sure! Let me download the paper with ID 12345678:
<execute_ipython>
download_arxiv_pdf("12345678")
</execute_ipython>

USER:
OBSERVATION:
[PDF: 12345678, Page 1]
[PDF content displayed.]

Assistant:
The paper with ID 12345678 has been downloaded successfully. The task is complete.
<task_finish>exit</task_finish>

Here is another example:
USER:
I opened an arxiv paper online.
Please check the content of the 10th page of the current arxiv paper.
[PDF: 12345678, Page 1]

Assistant:
Sure! Let's scroll the PDF to the 10th page by scrolling down 9 pages:
<execute_ipython>
scroll_pdf_page(direction = "down", pages = 9)
</execute_ipython>

USER:
[PDF: 12345678, Page 10]
[PDF content displayed.]

Assistant:
The content of the 10th page of the arxiv paper has been displayed successfully. The task is complete.
<task_finish>exit</task_finish>

USER: 
Please help me to view the video "lecture.mp4".

ASSISTANT:
Sure! Let me parse the video file "lecture.mp4" at 30 seconds:
<execute_ipython>
watch_video('lecture.mp4')
</execute_ipython>

USER:
[The video displayed.]

ASSISTANT:
The video has been displayed. 
<task_finish>
exit
</task_finish>
'''

tool_fake_user_response_prompt = '''You did not provide any commands. If you believe the task is complete or cannot be solved, reply with <task_finish>exit</task_finish>; otherwise, please provide a command.'''

tool_document = {
    "file_understand": tool_file_understand,
    "code_exec": tool_code_exe,
    "file_edit": tool_file_edit,
    "web_browse": tool_web_browse,
    "computer_interaction": tool_mk_operation
}

tool_example = {
    "code_exec": '',
    "file_understand": tool_file_understand_one_shot,
    "file_edit": tool_file_edit_one_shot,
    "web_browse": tool_web_browse_one_shot,
    "computer_interaction": tool_mk_one_shot
}

tool_stop = {
    "file_understand": ['</execute_ipython>', '</execute_bash>'],
    "code_exec": ['</execute_bash>', '</execute_ipython>'],
    "file_edit": ['</execute_ipython>', '</execute_bash>'],
    "web_browse": ['</execute_ipython>'],
    "computer_interaction": ['</execute_ipython>']
}

tool_note = {
    "file_understand": '',
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