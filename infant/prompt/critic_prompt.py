critic_analysis = '''Please help me determine if my previous analysis steps are wrong. If it is wrong, put the potential logic issue in <potential_issue>...</potential_issue> tags and provide them in a single sentence. 
Otherwise, return only "True" without any additional words and without using the <potential_issue>...</potential_issue> tags.'''

critic_system_prompt = '''User and Assistant collaborated to complete a task. Their conversation record is as follows. 
Please help me evaluate whether the task has been correctly completed.'''

critic_task_prompt_w_target ='''
Please check whether the Task: {task} Target: {target} have been achieved based on the previous conversation record. 
If the target is not achieved, tell me the reason.
If the target is achieved, please don't say any other things. Just say <|exit_code=0|>. 
'''

critic_task_prompt_wo_target ='''
Please check whether the Task: {task} has been correctly completed based on the previous conversation record. 
If the target is not achieved, tell me the reason.
If the target is achieved, please don't say any other things. Just say <|exit_code=0|>. 
'''