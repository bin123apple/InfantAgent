smy_potential_issue_pt= 'I reviewed our previous logic, and there seem to be some potential logical issues: {potential_issue}\n'

smy_new_code_pt= 'In order to solve the task above, I generated some new code: {new_code}\n'

smy_git_diff_pt= 'The git diff is shown below: {git_diff}\n'

smy_key_steps_pt= 'Here are some key steps: {key_steps}\n'

smy_reason_pt= '{reason}\n'

summary_sys_prompt = '''User and Assistant collaborated to complete a task. 
Their conversation record and the Git patch of the modified files are provided below. 
Please summarize the key steps taken to accomplish this task, focusing only on the essential and correct steps while ignoring errors and unnecessary actions.
Please output your key steps in the following format.
<key_steps>
1. Step 1
2. Step 2
...
n. Step n
</key_steps>.
'''

summary_prompt_true = '''The task has been successfully completed. The detailed conversation record and the git patch of the modified files are provided above. 
Please summarize the key steps we took to accomplish this task.
You should put All the key steps into the following tags: <key_steps>...</key_steps>.
for now, you don't need to tell me the next step.
'''

summary_prompt_false = '''The task does not appear to have been correctly completed. The detailed conversation record and the git patch of the modified files are provided above. 
Please summarize the key files and the main observations that I have and the reason why I can not complete the task.
You should put All the key steps into the following tags: <key_steps>...</key_steps>.
for now, you don't need to tell me the next step.
'''