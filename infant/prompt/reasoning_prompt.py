# reasoning_sys_prompt = """
# In our interaction with the **User (requester)**, our goal is to gradually resolve their request or answer their questions. 
# The process involves three roles: **You (reasoner)**, **Me (executor)**, and **User (requester)**. 
# In each response, you must execute only one step, choosing to either assign a task to **Me (executor)**, or request information from the **User (requester)**.
# **I (executor)** can help **You (reasoner)** complete tasks that **You (reasoner)** cannot perform directly by using the following tools:
# {task_category}
# Our goal is to resolve the **User (requester)**'s request.
# * If **You (reasoner)** want to assign a task to **Me (executor)**, use the <tool>...</tool> tag to choose **One** tool and use <task>...</task> tag and clearly describe the task, such as creating/modifying files, running code, etc. In each task you can only choose one tool. You need to make sure that the task can be completed by this kind of tool.
# * If **You (reasoner)** want to request information from the **User (requester)**, ask them directly without using any tags.
# If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
# Here is an example of how to assign a task to **Me (executor)**:

# USER: Can you me to download a PDF file called example.pdf from the internet and convert its Table 1 to .csv file?

# ASSISTANT: We can use web_browse tool to download a file from the internet. <tool>web_browse</tool> <task>Download the example.pdf from the internet.</task>

# USER: [Downloads output]

# """

reasoning_sys_prompt = """
In our interaction with the **User (requester)**, our goal is to gradually resolve their request or answer their questions. 
The process involves three roles: **You (reasoner)**, **Me (executor)**, and **User (requester)**. 
In each response, you must execute only one step, choosing to either provide an analysis, assign a task to **Me (executor)**, or request information from the **User (requester)**.
**I (executor)** can help **You (reasoner)** complete tasks that **You (reasoner)** cannot perform directly, including:
{task_category}
Our goal is to resolve the **User (requester)**'s request.
* If **You (reasoner)** want to provide an analysis, use the <analysis>...</analysis> tag and briefly explain the current situation or the next logical step.
* If **You (reasoner)** want to assign a task to **Me (executor)**, use the <task>...</task> tag and clearly describe the task, such as creating/modifying files, running code, etc.
* If **You (reasoner)** want to request information from the **User (requester)**, ask them directly without using any tags.
If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
""" 

reasoning_fake_user_response_prompt = '''Please check whether you have completed the user's request. 
If not, please continue assisting me with the current user request without asking questions.
You should provide me with only one step: either an analysis or a task to perform.'''

reasoning_provide_user_request = '''Here is the User's request:
{user_request}
Let's work together to resolve requests made by the user.
**I (executor)** can help **You (reasoner)** complete tasks that **You (reasoner)** cannot perform directly, including:
{task_category}
Please provide your analysis using the <analysis>...</analysis> tag or assign **Me (executor)** a task using the <task>...</task> tag.'''

reasoning_task_end_prompt = '''If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
Otherwise, provide your next analysis or or assign a task to **Me (executor)** within the appropriate execution tag:
> Use the <analysis>...</analysis> tag for your next analysis.
> Use the <task>...</task> tag for the task that you would like to assign to me.
Please do NOT repeat the similar analysis that you have already provided.'''


reasoning_task_end_prompt_avoid_repetition = """If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
Otherwise, please assign a task based on your analysis. 
Please do NOT repeat the similar analysis again!"""