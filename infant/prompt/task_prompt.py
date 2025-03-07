task_to_str_w_target = '''I generated some new files and code while trying to finish the last task, I will avoid to regenerate the same contents, here is a brief summary:
{summary}
Thought for the new task:
{thought}
Our current task is:
{task}
The expected target is:
{target}'''

task_to_str_wo_target = '''I generated some new files and code while trying to finish the last task, I will avoid to regenerate the same contents, here is a brief summary:
{summary}
Thought for the new task:
{thought}
Our current task is:
{task}'''

task_to_str_wo_summary_hands = '''Thought for the new task:
{thought}
Our current task is:
{task}
The expected target is:
{target}'''

task_to_str_wo_summary_wo_target_hands = '''Thought for the new task:
{thought}
Our current task is:
{task}'''

task_category = '''
1. I can help you edit files.
2. I can help you run code.
3. I can help you interact with the computer using the keyboard and mouse to complete any task that can be performed on it.
'''