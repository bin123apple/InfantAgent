#!/usr/bin/env python3
"""Rebuild dialogue.json from a saved trajectory.json.

`memory_list_to_dialogue()` works on live memory objects. This does the same
conversion from the serialized trajectory, so a run captured before that
function was fixed can still get its transcript without being re-run.

    python scripts/traj_to_dialogue.py runs/<stamp>/trajectory.json
"""

import json
import sys
from pathlib import Path


def render(m):
    """One trajectory entry -> zero or more chat turns."""
    t = m.get('_type')
    role = 'user' if m.get('source') == 'user' else 'assistant'
    thought = m.get('thought') or ''
    turns = []

    if t == 'Userrequest':
        turns.append({'role': 'user', 'content': m.get('text', '')})
    elif t == 'Message':
        turns.append({'role': role, 'content': thought})
    elif t == 'CmdRun':
        turns.append({'role': role,
                      'content': f"{thought}\n<execute_bash>\n{m.get('command','')}\n</execute_bash>"})
    elif t == 'IPythonRun':
        turns.append({'role': role,
                      'content': f"{thought}\n<execute_ipython>\n{m.get('code','')}\n</execute_ipython>"})
    elif t == 'Analysis':
        turns.append({'role': 'assistant', 'content': f"<analysis>{m.get('analysis','')}</analysis>"})
    elif t == 'Task':
        target = m.get('target')
        inner = f"<task>{m.get('task','')}"
        inner += f"<target>{target}</target></task>" if target is not None else "</task>"
        turns.append({'role': 'assistant', 'content': thought + inner})
    elif t == 'Finish':
        turns.append({'role': 'assistant', 'content': f"{thought}<finish>exit</finish>"})
    elif t == 'TaskFinish':
        turns.append({'role': role, 'content': f"{thought}<task_finish>exit</task_finish>"})
    elif t == 'Classification':
        turns.append({'role': 'assistant',
                      'content': f"<classification>{m.get('classification','')}</classification>"})

    if m.get('result') is not None:
        turns.append({'role': 'user', 'content': str(m['result'])})
    return turns


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    traj = Path(sys.argv[1])
    memories = json.loads(traj.read_text())

    dialogue = []
    for m in memories:
        dialogue.extend(render(m))

    out = traj.parent / 'dialogue.json'
    out.write_text(json.dumps(dialogue, ensure_ascii=False, indent=2))
    kinds = {}
    for m in memories:
        kinds[m.get('_type')] = kinds.get(m.get('_type'), 0) + 1
    print(f'{len(memories)} memories {kinds} -> {len(dialogue)} turns')
    print(f'wrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
