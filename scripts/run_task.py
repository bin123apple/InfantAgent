#!/usr/bin/env python3
"""Run one request through the agent and save the trajectory and the answer.

`infant/main.py` is an interactive prompt loop, and its `save_to_dataset()`
helper only works when the checkout is named `InfantAI` (it walks up looking for
that directory and raises otherwise -- this one is `InfantAgent`). This script
is the non-interactive equivalent: one request in, a self-contained run
directory out.

    python scripts/run_task.py --task "..."            # inline
    python scripts/run_task.py --task-file task.txt    # from a file

Writes to runs/<timestamp>/:
    task.txt          the request as given
    answer.md         the agent's final answer
    trajectory.json   every memory, raw (dataclasses.asdict)
    dialogue.json     the same trajectory as a chat transcript
    summary.txt       step counts, timing, agent end state
    screenshots/      whatever the agent captured
"""

import argparse
import asyncio
import dataclasses
import json
import os
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

# Load .env before importing infant.config -- the API key is read at import time.
env_file = REPO / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault('INFANT_DOCKERLESS', '1')
os.environ.setdefault('DISPLAY', ':10')

from infant.config import Config                     # noqa: E402
from infant.main import initialize_agent, run_single_step, cleanup  # noqa: E402
from infant.util.save_dataset import memory_list_to_dialogue        # noqa: E402
import infant.util.constant as constant              # noqa: E402


def serialize(memory_list):
    """Raw dump of the memory dataclasses, tolerant of unserializable fields."""
    out = []
    for m in memory_list:
        try:
            d = dataclasses.asdict(m)
        except Exception:
            d = {k: v for k, v in vars(m).items()}
        # asdict() only returns declared dataclass fields; `source` and
        # `output` are set as plain instance attributes (parser.py), so they
        # would otherwise be missing from the trajectory.
        for extra in ('source', 'output'):
            if extra not in d and hasattr(m, extra):
                d[extra] = getattr(m, extra)
        d['_type'] = type(m).__name__
        out.append(json.loads(json.dumps(d, default=str, ensure_ascii=False)))
    return out


async def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--task', help='the request text')
    src.add_argument('--task-file', help='file containing the request')
    ap.add_argument('--out', default=str(REPO / 'runs'), help='output root')
    ap.add_argument('--no-oss-llm', action='store_true',
                    help='disable the UI-TARS visual-grounding model (needs a '
                         'vLLM server on :8888); GUI clicking by coordinates '
                         'will not work, browser/DOM and shell tools still do')
    args = ap.parse_args()

    task = Path(args.task_file).read_text() if args.task_file else args.task
    task = task.strip()

    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    run_dir = Path(args.out) / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'task.txt').write_text(task + '\n')
    print(f'[run_task] output -> {run_dir}')

    config = Config()
    config.finalize_config()
    if args.no_oss_llm:
        config.use_oss_llm = False

    agent = computer = None
    answer, err = '', None
    t0 = time.time()
    try:
        agent, computer = await initialize_agent(config)
        constant.MOUNT_PATH = computer.workspace_mount_path
        print(f'[run_task] agent ready in {time.time() - t0:.0f}s; running task')
        t1 = time.time()
        answer = await run_single_step(agent, task)
        print(f'[run_task] task finished in {time.time() - t1:.0f}s')
    except Exception as e:
        err = traceback.format_exc()
        print(f'[run_task] FAILED: {type(e).__name__}: {e}', file=sys.stderr)
    finally:
        memories = list(agent.state.memory_list) if agent else []
        state = getattr(agent.state, 'agent_state', None) if agent else None

        (run_dir / 'answer.md').write_text(answer or '')
        (run_dir / 'trajectory.json').write_text(
            json.dumps(serialize(memories), ensure_ascii=False, indent=2))
        try:
            dialogue = memory_list_to_dialogue(memories)
        except Exception as e:
            print(f'[run_task] dialogue.json empty: {type(e).__name__}: {e}',
                  file=sys.stderr)
            dialogue = []
        (run_dir / 'dialogue.json').write_text(
            json.dumps(dialogue, ensure_ascii=False, indent=2))

        counts = {}
        for m in memories:
            counts[type(m).__name__] = counts.get(type(m).__name__, 0) + 1
        summary = [
            f'task chars   : {len(task)}',
            f'elapsed      : {time.time() - t0:.0f}s',
            f'agent state  : {state}',
            f'memories     : {len(memories)}',
            *(f'  {k:<20} {v}' for k, v in sorted(counts.items())),
            f'answer chars : {len(answer or "")}',
        ]
        if err:
            summary += ['', 'ERROR:', err]
        (run_dir / 'summary.txt').write_text('\n'.join(summary) + '\n')

        # The agent writes screenshots into the sandbox workspace; keep them
        # with the run rather than leaving them to the next run's wipe.
        shots = Path(computer.computer_workspace_dir) / 'screenshots' if computer else None
        if shots and shots.is_dir():
            shutil.copytree(shots, run_dir / 'screenshots', dirs_exist_ok=True)

        if agent:
            try:
                await cleanup(agent, computer)
            except Exception:
                pass

        print('\n'.join(summary))
        print(f'\n[run_task] saved to {run_dir}')

    return 0 if answer else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
