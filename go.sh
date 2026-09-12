#!/bin/bash
# One-click task run. Edit TASK below, then: ./go.sh
#
# Everything else is handled: preflight + desktop (via run.sh --check), the
# venv, .env, dockerless mode, and a run directory with the full trajectory.
#
#   ./go.sh                      run the TASK written below
#   ./go.sh "open a terminal"    run this task instead, TASK ignored
#   ./go.sh -f task.txt          run the task in a file
#   ./go.sh --tail               also follow llm_trace.jsonl live in this shell

# ============================ EDIT THIS ============================
TASK='Open a terminal on the desktop, run `uname -a`, and tell me the kernel version.'
# ===================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${INFANT_VENV:-/workspace/.infant/venv}"
cd "$REPO_DIR"

TAIL=0
ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --tail)  TAIL=1; shift ;;
        -f|--task-file) ARGS=(--task-file "$2"); shift 2 ;;
        -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
        *)       TASK="$1"; shift ;;
    esac
done
[ ${#ARGS[@]} -eq 0 ] && ARGS=(--task "$TASK")

# Preflight and the Xvfb desktop, without starting the backend. Idempotent:
# a desktop that is already up is left alone.
./run.sh --check

# shellcheck disable=SC1091
source "$VENV/bin/activate"
export INFANT_DOCKERLESS=1
export DISPLAY="${DISPLAY:-:10}"

# The agent clears the sandbox workspace on init, and repeated inits leak
# kernel-gateway processes from earlier runs; both are cheap to redo here.
pkill -f kernelgateway >/dev/null 2>&1 || true
pkill -f execute_server.py >/dev/null 2>&1 || true

RUN_ROOT="$REPO_DIR/runs"
printf '\n\033[2m==>\033[0m Running task\n  %s\n\n' "${TASK:0:120}"

if [ "$TAIL" = 1 ]; then
    # Follow the trace as it is written: the run directory does not exist yet,
    # so wait for the newest one to appear before tailing.
    ( before="$(ls "$RUN_ROOT" 2>/dev/null | tail -1 || true)"
      for _ in $(seq 1 600); do
          now="$(ls "$RUN_ROOT" 2>/dev/null | tail -1 || true)"
          [ -n "$now" ] && [ "$now" != "$before" ] && break
          sleep 1
      done
      tail -f "$RUN_ROOT/$now/llm_trace.jsonl" 2>/dev/null | \
          python3 -c 'import json,sys
for l in sys.stdin:
    try: r = json.loads(l)
    except Exception: continue
    tag = f"{r[\"kind\"]}/{r.get(\"role\")}"
    body = r.get("response") or " | ".join(
        str(m["content"])[:120] for m in r.get("messages", [])[-1:])
    print(f"  [{r[\"seq\"]:>3}] {tag:<26} {str(body)[:160]}", flush=True)' ) &
    TAILPID=$!
    trap 'kill $TAILPID 2>/dev/null || true' EXIT
fi

python scripts/run_task.py "${ARGS[@]}"

LATEST="$(ls -d "$RUN_ROOT"/*/ 2>/dev/null | tail -1)"
if [ -n "$LATEST" ]; then
    printf '\n\033[2m==>\033[0m Trajectory\n'
    ls -la "$LATEST" | sed 's/^/  /'
    printf '\n  answer:     %sanswer.md\n  steps:      %sconsole.log\n  llm calls:  %sllm_trace.jsonl\n' \
        "$LATEST" "$LATEST" "$LATEST"
fi
