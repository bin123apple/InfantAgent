#!/bin/bash
# One-command launcher for InfantAgent in dockerless mode.
#
# Containers cannot be created in this environment (namespace syscalls are
# blocked by seccomp), so the agent's sandbox is this host itself: a local Xvfb
# desktop plus a local bash session instead of a container reached over SSH.
# See SETUP_NOTES.md for why podman/rootless Docker do not help.
#
#   ./run.sh              start the desktop and the backend
#   ./run.sh --cli        drive the agent from the terminal; no ports at all
#   ./run.sh --no-vnc     skip x11vnc/noVNC (only a human viewer needs them)
#   ./run.sh --check      run the preflight checks only, then exit
#   ./run.sh --port 9000  serve the backend on a different port
#   ./run.sh --no-install skip apt installs, fail if something is missing
#
# Everything here is idempotent: re-running only fixes what is not already in
# place.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Note the dot: the agent clears /workspace on every init with `rm -rf *`, and
# that glob does not match dot-entries. A venv at /workspace/infant/venv gets
# deleted; this one does not. Computer.setup_local_computer() asserts it.
VENV="${INFANT_VENV:-/workspace/.infant/venv}"
export DISPLAY="${DISPLAY:-:10}"
export INFANT_NOVNC_PORT="${INFANT_NOVNC_PORT:-6080}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
VG_URL="http://127.0.0.1:8888"          # UI-TARS visual-grounding server

CHECK_ONLY=0
ALLOW_INSTALL=1
CLI_MODE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --check)      CHECK_ONLY=1; shift ;;
        --no-install) ALLOW_INSTALL=0; shift ;;
        --no-vnc)     export NO_VNC=1; shift ;;
        --cli)        CLI_MODE=1; shift ;;
        --port)       BACKEND_PORT="$2"; shift 2 ;;
        -h|--help)    sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        *)            echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
done

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; DIM=$'\033[2m'; RST=$'\033[0m'
ok()   { echo "  ${GRN}ok${RST}   $*"; }
warn() { echo "  ${YLW}warn${RST} $*"; }
fail() { echo "  ${RED}fail${RST} $*"; }
step() { echo; echo "${DIM}==>${RST} $*"; }

cd "$REPO_DIR"

# Load secrets from .env (gitignored) if present, without overriding anything
# already exported in the environment.
if [ -f "$REPO_DIR/.env" ]; then
    while IFS='=' read -r k v; do
        case "$k" in ''|'#'*) continue ;; esac
        [ -n "${!k:-}" ] || export "$k=$v"
    done < "$REPO_DIR/.env"
fi

# --- 1. host packages ---------------------------------------------------
step "Host packages"
MISSING=""
for bin_pkg in "Xvfb:xvfb" "x11vnc:x11vnc" "xdotool:xdotool" "scrot:scrot" \
               "openbox:openbox" "websockify:websockify" "xdpyinfo:x11-utils" "xauth:xauth" \
               "xterm:xterm" "xsetroot:x11-xserver-utils"; do
    bin="${bin_pkg%%:*}"; pkg="${bin_pkg##*:}"
    command -v "$bin" >/dev/null 2>&1 || MISSING="$MISSING $pkg"
done
[ -d /usr/share/novnc ] || MISSING="$MISSING novnc"

if [ -n "$MISSING" ]; then
    MISSING="$(echo $MISSING | tr ' ' '\n' | sort -u | tr '\n' ' ')"
    if [ "$ALLOW_INSTALL" = 1 ]; then
        warn "installing:$MISSING"
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $MISSING >/dev/null
        ok "installed"
    else
        fail "missing:$MISSING (drop --no-install, or: apt-get install$MISSING)"
        exit 1
    fi
else
    ok "all present"
fi

# PYTHON_SETUP_CODE looks for google-chrome-stable specifically; without it the
# agent still runs, but its browser tooling does not.
if command -v google-chrome-stable >/dev/null 2>&1; then
    ok "google-chrome-stable $(google-chrome-stable --version 2>/dev/null | awk '{print $3}')"
else
    warn "google-chrome-stable not installed -- browser tools will fail"
    warn "  curl -fsSLo /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
    warn "  apt-get install -y /tmp/chrome.deb"
fi

# --- 2. virtualenv ------------------------------------------------------
step "Virtualenv ($VENV)"
if [ ! -x "$VENV/bin/python3" ]; then
    fail "not found. Recreate it with:"
    echo "      export UV_PROJECT_ENVIRONMENT=$VENV"
    echo "      uv sync --frozen --no-install-project"
    exit 1
fi
ok "found"

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# setup.sh shells out to `python -m pip`, but `uv sync` does not install pip.
if ! python3 -m pip --version >/dev/null 2>&1; then
    warn "no pip in the venv; installing via ensurepip"
    python3 -m ensurepip --upgrade >/dev/null 2>&1
    ok "pip installed"
else
    ok "pip $(python3 -m pip --version 2>/dev/null | awk '{print $2}')"
fi

# The PyPI `pathlib` package is the Python-2 backport; on 3.10+ it shadows the
# stdlib module and dies on `from collections import Sequence`, breaking every
# import of pathlib. pyxnat drags it in through the lockfile, so `uv sync`
# brings it back and it has to be removed again.
SITE="$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
if [ -f "$SITE/pathlib.py" ]; then
    warn "removing the bogus 'pathlib' backport from the venv (see SETUP_NOTES.md)"
    rm -rf "$SITE/pathlib.py" "$SITE/pathlib-1.0.1.dist-info"
    ok "removed"
fi
PATHLIB_SRC="$(python3 -c 'import pathlib, sysconfig
print("stdlib" if pathlib.__file__.startswith(sysconfig.get_paths()["stdlib"]) else pathlib.__file__)')"
if [ "$PATHLIB_SRC" = stdlib ]; then
    ok "pathlib resolves to the stdlib"
else
    fail "pathlib resolves to $PATHLIB_SRC -- imports will break"
    exit 1
fi

# --- 3. stale kernel processes -----------------------------------------
step "Stale Jupyter processes"
# Each Computer() init starts its own kernel gateway + execute server and does
# not reap the previous ones; leftovers make execute_cli.py talk to a dead port.
STALE="$(pgrep -f 'kernelgateway|execute_server\.py' 2>/dev/null | tr '\n' ' ' || true)"
if [ -n "${STALE// /}" ]; then
    warn "killing leftovers: $STALE"
    pkill -f kernelgateway 2>/dev/null || true
    pkill -f 'execute_server\.py' 2>/dev/null || true
    sleep 1
    pgrep -f 'kernelgateway|execute_server\.py' >/dev/null 2>&1 \
        && pkill -9 -f 'kernelgateway|execute_server\.py' 2>/dev/null || true
    ok "cleaned"
else
    ok "none"
fi

# --- 4. desktop ---------------------------------------------------------
step "Desktop"
bash "$REPO_DIR/scripts/start_local_desktop.sh" | sed 's/^/  /'

# --- 5. model endpoints -------------------------------------------------
step "Models"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    ok "ANTHROPIC_API_KEY is set"
elif grep -qE '^\s*api_key\s*=\s*"[^"]+"' config.toml 2>/dev/null; then
    ok "api_key found in config.toml"
else
    warn "no API key in ANTHROPIC_API_KEY or config.toml"
    warn "  export it, edit config.toml, or enter it in the frontend 'setting' panel"
fi

# config.use_oss_llm defaults to True and expects UI-TARS served here.
if curl -fsS -m 2 -o /dev/null "$VG_URL/v1/models" 2>/dev/null; then
    ok "visual-grounding model reachable at $VG_URL"
else
    warn "no visual-grounding model at $VG_URL (config.use_oss_llm is True)"
    warn "  serve it with, e.g.:"
    warn "    CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \\"
    warn "      --model ByteDance-Seed/UI-TARS-1.5-7B --port 8888"
    warn "  or set config.use_oss_llm = False to skip visual grounding"
fi

# --- 6. launch ----------------------------------------------------------
if [ "$CHECK_ONLY" = 1 ]; then
    step "Preflight complete (--check); not starting the backend."
    exit 0
fi

export INFANT_DOCKERLESS=1

if [ "$CLI_MODE" = 1 ]; then
    step "Starting the agent (CLI)"
    echo "  display  $DISPLAY"
    echo "  ${DIM}no ports needed: type your request at the prompt${RST}"
    echo
    exec python3 -m infant.main
fi

step "Starting backend"
[ "${NO_VNC:-0}" = 1 ] || echo "  desktop  http://localhost:$INFANT_NOVNC_PORT/vnc.html"
echo "  backend  http://localhost:$BACKEND_PORT  (docs at /docs)"
echo "  display  $DISPLAY"
echo "  ${DIM}first start takes ~45s: vLLM/CUDA imports${RST}"
echo

exec uvicorn backend:app --host 0.0.0.0 --port "$BACKEND_PORT" --log-level info
