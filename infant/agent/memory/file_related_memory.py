import re
from infant.sandbox.sandbox import Sandbox
from infant.util.logger import infant_logger as logger

def get_diff_patch(sandbox: Sandbox):
    
    exit_code, output = sandbox.execute(f'cd {sandbox.workspace_git_path}')

    exit_code, output = sandbox.execute('git config --global core.pager ""')
    
    # check the modified files
    exit_code, output = sandbox.execute('git -c color.status=false status -s')
    if exit_code != 0:
        logger.error('Failed to get the status of files')
        return ''

    # Mark the modified files
    modified_files = []
    for line in output.splitlines():
        logger.info(f'Checking git status: {line}')
        if all(keyword not in line.strip() for keyword in ('.backup.', 'screenshots/')):
            # file name after 'M'
            modified_files.append(line[2:].strip())

    # if there is no modified files
    if not modified_files:
        logger.info('No modified files to add')
        return ''

    # Add all the modified files to the repo
    for file in modified_files:
        if 'color.status=false status -s' in file:
            continue
        logger.info(f"Executing `git add {file}`")
        exit_code, output = sandbox.execute(f'git add {file}')
        if exit_code != 0:
            logger.error(f'Failed to add file to index: {file}')
            return ''
        
    # get the git diff
    exit_code, git_patch = sandbox.execute(
        f'git diff --no-color --cached'
    , timeout=30)
    if exit_code != 0:
        logger.error('Failed to get git diff')
        return ''

    cleaned_patch_lines = []
    for line in git_patch.splitlines():
        if re.match(r'^(diff|index|@@|---|\+\+\+)', line):
            continue 
        cleaned_line = re.sub(r'^([+-])', '', line)
        if cleaned_line.strip():
            cleaned_patch_lines.append(cleaned_line)

    cleaned_git_patch = '\n'.join(cleaned_patch_lines)
    return cleaned_git_patch


def git_add_or_not(user_response, sandbox: Sandbox):
    """
    This function is used to add the modified files to the git repo and get the git diff.
    If the user approves the patch, it will commit the changes.
    If the user rejects the patch, it will undo the last git add.
    """
    # git add
    get_diff_patch(sandbox)
    
    # git commit 
    if user_response:
        # User approved the patch, do nothing
        logger.info("User approved the patch, no changes made.")
        # commit_msg.replace('"', '\"')
        commit_msg = 'Finish a task'
        exit_code, output = sandbox.execute(f'git commit -m "{commit_msg}"')
        if exit_code != 0:
            logger.error(f'Failed to commit the changes: {output}')
            return 'Error: Failed to commit the changes.'
        else:
            logger.info("Git has been committed successfully.")
            return 'PR got approved and it has been committed successfully.'
    else:
        # User rejected the patch, undo the last git add
        logger.info("User rejected the patch, resetting the last git add.")
        exit_code, output = sandbox.execute(f'git reset && git clean -f')
        if exit_code != 0:
            logger.error(f'Failed to reset the git add: {output}')
            return 'Error: Failed to reset git add.'
        else:
            logger.info("Git add has been reset successfully.")
            return 'Patch rejected, git add reset successfully.'
        
        
def get_final_git_diff(sandbox: Sandbox):      
    exit_code, output = sandbox.execute(f'git log --pretty=format:%H -n 1 --grep="base commit"')

    if exit_code == 0:
        base_commit_hash = output.strip()
        logger.info(f'Base commit hash: {base_commit_hash}')
    else:
        return f'Failed to find base commit: {output}'

    exit_code, output = sandbox.execute(f'cd /workspace')
    exit_code, output = sandbox.execute(f'git diff {base_commit_hash}')

    if exit_code == 0:
        return f'Git diff with base commit:\n{output}'
    else:
        return f'Failed to get git diff with base commit: {output}'
    
    
def get_reset_to_base_commit(sandbox):      
    exit_code, output = sandbox.execute(f'git log --pretty=format:%H -n 1 --grep="base commit"')

    if exit_code == 0:
        base_commit_hash = output.strip()
        logger.info(f'Base commit hash: {base_commit_hash}')
    else:
        logger.info(f'Failed to find base commit: {output}')

    exit_code, output = sandbox.execute(f'cd /workspace')
    exit_code, output = sandbox.execute(f'git reset --hard {base_commit_hash}')

    if exit_code == 0:
        logger.info(f'Finished resetting to base commit')
    else:
        logger.info(f'Failed to reset to base commit')

def remove_ansi_escape_sequences(text):
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def convert_git_diff_to_python_files(git_diff):
    python_files_changes = {}

    file_regex = re.compile(r'^diff --git a/.+\.py b/(.+\.py)')
    line_change_regex = re.compile(r'^@@ .+ @@')

    current_file = None
    current_file_content = []
    in_hunk = False

    for line in git_diff.splitlines():
        file_match = file_regex.match(line)
        if file_match:
            if current_file and current_file_content:
                python_files_changes[current_file] = "\n".join(current_file_content)
            current_file = file_match.group(1)
            current_file_content = []
            in_hunk = False
            continue

        if line_change_regex.match(line):
            in_hunk = True
            continue

        if in_hunk and current_file:
            if line.startswith('+') and not line.startswith('+++'):
                current_file_content.append(line[1:])
            elif not line.startswith('-') and not line.startswith('---') and not line.startswith('+++') and not line.startswith('\\'):
                current_file_content.append(line)

    if current_file and current_file_content:
        python_files_changes[current_file] = "\n".join(current_file_content)

    return python_files_changes

