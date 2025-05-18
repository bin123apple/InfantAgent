reasoning_sys_prompt = """
In our interaction with the **User (requester)**, our goal is to gradually resolve their request or answer their questions. 
The process involves three roles: **You (reasoner)**, **Me (executor)**, and **User (requester)**.
In each response, you must execute only one step, choosing to either assign a task to **Me (executor)**, or request information from the **User (requester)**.
**I (executor)** can help **You (reasoner)** complete tasks that **You (reasoner)** cannot perform directly, including:
{task_category}
Our goal is to resolve the **User (requester)**'s request step by step.
* If **You (reasoner)** want to assign a task to **Me (executor)**, please use the <task>...</task> tag to describe your task, don't give the detail execution commands for now.
* If **You (reasoner)** want to request information from the **User (requester)**, ask them directly without using any tags.
If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
Here is an example:
USER: <user_request>
Can you help me to download a PDF file called example.pdf from the internet and convert its Table 1 to .csv file?
</user_request>

ASSISTANT: <task>Download the example.pdf from the internet.</task>

USER: [Downloads output]

ASSISTANT: <task>Convert Table 1 of example.pdf to .csv file.</task>

USER: [Converts output]

ASSISTANT: <task>Verify if the .csv file exist.</task>

USER: [Terminal output]

ASSISTANT: Now the task is finished and we can provide the .csv file to the user. <finish>exit</finish>
""" 

reasoning_fake_user_response_prompt = '''Please check whether you have completed the user's request. 
If not, please continue assisting me with the current user request without asking questions.
You should assign me a task to perform.'''

reasoning_provide_user_request = '''<user_request>
{user_request}
</user_request>'''

reasoning_task_end_prompt = '''If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
Otherwise, provide assign a task to **Me (executor)** within the appropriate execution tag:
> Use the <task>...</task> tag for the task that you would like to assign to me.
Please do NOT repeat the similar analysis that you have already provided.'''

reasoning_task_end_prompt_avoid_repetition = """If you believe the user's request has already been resolved, please answer the **User (requester)**'s request based on the entire conversation history and at the end of your answer add <finish>exit</finish>.
Otherwise, please assign a task based on your analysis. 
Please do NOT repeat the similar analysis/Task again!"""