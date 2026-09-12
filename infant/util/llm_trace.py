"""Every LLM exchange, appended to one JSONL file as it happens.

`logger.py` defines `llm_prompt_logger` and `llm_response_logger`, but nothing
in the repo ever calls them -- so prompts and responses were never persisted
and only the *parsed* steps reached the console. This writes the raw exchange
instead: one JSON object per line, flushed per call, so a run can be inspected
while it is still going and replayed afterwards.

Inert unless `INFANT_TRACE_FILE` names a path (`scripts/run_task.py` and
`go.sh` point it at the run directory), so importing this costs nothing in the
backend or the eval harness.

Image parts are replaced by `<image: N bytes>`: one screenshot is ~2 MB of
base64 per call, it would dwarf the text, and `screenshots/` already keeps the
pixels.
"""

import json
import os
import threading
import time

_lock = threading.Lock()
_seq = 0

# 4 KB of a single string is already more than anyone reads in a trace; the
# full text lives in trajectory.json.
_MAX_CHARS = int(os.getenv('INFANT_TRACE_MAX_CHARS', '20000'))


def trace_file() -> str | None:
    """Read the env var per call: run_task.py sets it after this is imported."""
    return os.getenv('INFANT_TRACE_FILE') or None


def _clip(s: str) -> str:
    if len(s) <= _MAX_CHARS:
        return s
    return s[:_MAX_CHARS] + f'\n...[clipped {len(s) - _MAX_CHARS} chars]'


def _scrub(content):
    """Keep the text, drop the image bytes, preserve the structure."""
    if isinstance(content, str):
        return _clip(content)
    if isinstance(content, list):
        out = []
        for part in content:
            if not isinstance(part, dict):
                out.append(_clip(str(part)))
                continue
            if part.get('type') == 'image_url':
                url = (part.get('image_url') or {}).get('url', '')
                out.append({'type': 'image', 'bytes': len(url)})
            elif part.get('type') == 'text':
                out.append({'type': 'text', 'text': _clip(part.get('text', ''))})
            else:
                out.append({'type': part.get('type', 'unknown')})
        return out
    return _clip(str(content))


def _messages(messages) -> list:
    out = []
    for m in messages or []:
        if isinstance(m, dict):
            out.append({'role': m.get('role'), 'content': _scrub(m.get('content'))})
        else:
            out.append({'role': None, 'content': _clip(str(m))})
    return out


def trace(kind: str, model: str, *, messages=None, response=None, **meta) -> None:
    """Append one exchange. Never raises -- tracing must not break a run."""
    path = trace_file()
    if not path:
        return
    global _seq
    try:
        with _lock:
            _seq += 1
            record = {'seq': _seq, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                      'kind': kind, 'model': model}
            if messages is not None:
                record['messages'] = _messages(messages)
            if response is not None:
                record['response'] = _clip(str(response))
            record.update(meta)
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    except Exception:
        pass
