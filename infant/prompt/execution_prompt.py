execution_split_userrequest_prompt = '''Please help me break the user's request into smaller tasks, and I will complete them one by one.'''

execution_critic_false_prompt = '''The task is not finished'''

execution_critic_true_prompt = '''The task is finished'''

execution_task_end_prompt = '''If you think the current task: {task} is already solved, please respond with your conclusion and include the following tag at the end:
<task_finish>
exit
</task_finish>. 
Otherwise, provide the next command within the appropriate execution tag:
> Use <execute_bash>...</execute_bash> for Bash commands.
> Use <execute_ipython>...</execute_ipython> for my other customized commands, as I mentioned in the beginning.
Please don't take any steps on your own that aren NOT related to completing the current task: {task}; I will guide you through the next steps. 
You only need to ensure that the current task is completed.'''