clf_sys_prompt = '''
I would like to finish a task, please help me choose the suitable sets of commands to complete this task.
1. File editing related commands: This set of commands can be used to view file content, as well as perform additions, deletions, searches, and modifications on files. If you want to select this set of commands, please return: <clf_task>file_edit</clf_task>
2. Code execution related commands: This set of commands can be used to execute code snippets. If you want to select this set of commands, please return: <clf_task>code_exec</clf_task>
3. Computer interaction commands: These commands can be used to interact with the computer via the keyboard and mouse. If you want to select this set of commands, please return: <clf_task>computer_interaction</clf_task>
If you want to select multiple sets of commands, please separate them with commas. 
For example, if you think we not only need to edit some files but also execute some code, you should return: <clf_task>file_edit, code_exec</clf_task>.
'''

clf_task_to_str_w_target = '''I would like to finish the task below:
{task}
The expected target is:
{target}
Please help me choose the commands to complete this task.
'''

clf_task_to_str_wo_target = '''I would like to finish the task below:
{task}
Please help me choose the commands to complete this task.
'''