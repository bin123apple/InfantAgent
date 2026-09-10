# Running InfantAgent without Docker

InfantAgent normally runs its sandbox as a privileged container: a systemd
Ubuntu image with GNOME, xrdp and Guacamole, which the agent drives over SSH and
RDP. On hosts where containers cannot be created at all, that path is closed.

It turns out the container was never the point. The agent drives the GUI with
`xdotool` and grabs frames with PIL (`infant/tools/computer_use/computeruse.py`),
both over a shell; Docker only ever supplied "a Linux box with a `$DISPLAY`", and
RDP/Guacamole existed so a **human** could watch. Both can be replaced with plain
user-space processes.

This mode swaps the container for:

| Container provided | Dockerless replacement |
|---|---|
| A Linux box reached over SSH | A local `bash` session (`infant/computer/local_shell.py`) |
| A GNOME desktop on `$DISPLAY` | `Xvfb :10` + `openbox` |
| RDP + Guacamole for a human viewer | `x11vnc` + noVNC (optional) |
| UI-TARS on a GPU for grounding | Still UI-TARS, or an API vision model (`infant/llm/llm_vg_api.py`) |

**It removes the sandbox.** The agent runs as your user, directly on the host,
and can modify anything that user can. See [Isolation](#isolation) before running
anything you would not run yourself.

---

## 1. Environment

Verified on Ubuntu 24.04, Python 3.11/3.12, `uv` 0.9, 1x A100-80GB (the GPU is
only needed if you serve UI-TARS locally).

### Python environment (uv)

The lockfile is the reproducible, author-tested set — install from it, not from
`pyproject.toml`. Installing unpinned pulls `uvicorn 0.52` / `aiohttp 3.14`,
which break `backend.py` at import time.

```bash
export UV_CACHE_DIR=/path/for/cache
export UV_PROJECT_ENVIRONMENT=/path/for/venv     # ~20 GB; put it on a big disk
uv sync --frozen --no-install-project
```

Two things the lockfile does not give you, both of which `run.sh` repairs on
every start (so you can skip them if you use `run.sh`):

- **`pip` is missing.** `uv sync` does not install one, and the agent's
  `tools/setup.sh` shells out to `python -m pip`. Fix: `python -m ensurepip --upgrade`.
- **The `pathlib` backport is present and breaks everything.** `pyxnat` pulls
  PyPI `pathlib` 1.0.1 in through the lockfile (`uv.lock`); it is the Python-2
  backport, it shadows the stdlib module on 3.10+, and it dies on
  `from collections import Sequence`. Fix: delete `site-packages/pathlib.py` and
  `site-packages/pathlib-1.0.1.dist-info`. **`uv sync` brings it back**, so
  re-delete after any sync.

### Host packages

```bash
apt-get install -y xvfb x11vnc xdotool scrot openbox xterm \
                   novnc websockify x11-utils xauth x11-xserver-utils
```

Google Chrome is required by `PYTHON_SETUP_CODE`, which looks for
`google-chrome-stable` specifically:

```bash
curl -fsSLo /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y /tmp/chrome.deb
```

### Where the venv may live

The agent **clears its workspace on every run** (`initialize_agent()` in
`infant/main.py`). The workspace path is `/workspace` and cannot be moved — the
tools hard-code it (`computeruse.py` writes screenshots to
`/workspace/screenshots`), as does the sandbox↔host path translation.

So nothing else may sit in `/workspace` unprotected. The wipe is a plain
`rm -rf *`, whose glob does not match dot-entries, so a venv at
`/workspace/.infant/venv` survives while `/workspace/infant/venv` is destroyed.
`Computer.setup_local_computer()` asserts this at startup rather than letting you
discover it as a deleted venv. A `.gitignore` is also written into the workspace,
because `initialize_agent()` then runs `git add .`, which *does* descend into
dot-directories.

### API key

Put it in `.env` (already gitignored); `run.sh` loads it without overriding
anything already exported.

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Visual grounding (optional GPU)

`config.use_oss_llm` selects the grounding model:

- `True` → UI-TARS-1.5-7B via vLLM. Needs a GPU and a ~31 GB download.
- `False` → `LLM_VG_API`, any litellm vision model. No GPU.

To serve UI-TARS:

```bash
HF_HOME=/big/disk/hf HF_HUB_DISABLE_XET=1 CUDA_VISIBLE_DEVICES=0 \
python -m vllm.entrypoints.openai.api_server \
  --model ByteDance-Seed/UI-TARS-1.5-7B --port 8889 --host 127.0.0.1 \
  --max-model-len 32768 --gpu-memory-utilization 0.85 --limit-mm-per-prompt image=4
```

Then point the agent at it — `base_url_oss` honours `INFANT_VG_URL`:

```
INFANT_VG_URL=http://127.0.0.1:8889
```

Note the port. `base_url_oss` defaults to 8888, which is also JupyterLab's
default; images that already run one (RunPod's, for example) collide.
`HF_HUB_DISABLE_XET=1` avoids a chunk cache that duplicates the download.

Measured accuracy, locating element centres on a 1920x1080 screenshot (median
error over synthetic targets down to 18x18 px, exact ground truth):

| model | median error |
|---|---|
| `claude-opus-4-8` | **1.0 px** |
| UI-TARS-1.5-7B | 8.5 px |

The API model is the more accurate of the two here, and needs no GPU, but bills
about $0.015 per grounding call. Its accuracy depends on **not** over-shrinking
the screenshot: Opus 4.7+ accepts 2576 px on the long edge, so a 1920x1080 frame
passes through untouched, while older models cap at 1568 px and the resampling
alone cost ~100 px of accuracy. `LLM_VG_API` applies Anthropic's documented
scale formula per model and maps the returned coordinates back.

---

## 2. Running

```bash
./run.sh                # preflight + desktop + backend on :8000
./run.sh --cli          # drive the agent from the terminal; no ports at all
./run.sh --no-vnc       # skip x11vnc/noVNC (only a human viewer needs them)
./run.sh --check        # run the checks only, start nothing
./run.sh --port 9000    # serve the backend elsewhere
./run.sh --no-install   # never apt-get; fail instead if something is missing
```

`run.sh` is idempotent. On every start it installs missing host packages, adds
`pip` to the venv, deletes the `pathlib` backport if `uv sync` brought it back,
reaps leaked Jupyter kernel-gateway/execute-server processes from earlier runs
(each `Computer()` starts a pair and never reaps them), brings the desktop up,
and warns without blocking about a missing API key or grounding server.

Watch the desktop at `http://localhost:6080/vnc.html` — note the path; `/`
also answers but the page is `vnc.html`. Nobody has to watch it: with x11vnc and
noVNC stopped entirely, the agent still opens windows, finds them with `xdotool`,
clicks, types and screenshots. Only **Xvfb plus a window manager** are required.

If the ports are unreachable (a pod that exposes only SSH, say), `--cli` runs
`python -m infant.main`, an interactive request loop, over a plain SSH session.

### One task, non-interactively

```bash
python scripts/run_task.py --task "..."             # inline
python scripts/run_task.py --task-file task.txt     # from a file
```

Writes `runs/<timestamp>/`: `answer.md`, `trajectory.json`, `dialogue.json`,
`summary.txt`, `screenshots/`. The repo's own `save_to_dataset()` cannot be used
here — it walks up looking for a directory named `InfantAI` and raises when the
checkout is named anything else.

**Copy anything you want to keep out of `/workspace` before the next run**, which
wipes it.

---

## 3. Isolation

There is none. The container was the sandbox; dockerless has no replacement for
it. The agent runs as your user and can modify the repo, the venv and anything
else that user can reach. Two guards exist, and they are narrow:

- `initialize_agent()` refuses to clear a workspace that resolves to a system
  directory (`_PROTECTED_DIRS` in `infant/main.py`).
- `setup_local_computer()` refuses to start if the venv sits somewhere the
  workspace wipe would reach.

Everything else is unguarded. Chrome runs with `--no-sandbox` (it will not start
as root otherwise), and `init_plugins()` overwrites `~/.bashrc` (dockerless
copies it to `~/.bashrc.infant-backup` first) and sets a global git identity of
`infant <infant@ai.com>`. Fine for experimenting on a machine you own; not for
untrusted tasks. Running the agent as a dedicated unprivileged user would be the
obvious next step and is not implemented here.

---

## 4. Why podman / rootless Docker do not help

This is not a privilege problem — the failing host was already uid 0. Namespace
*syscalls* are blocked by the outer container's seccomp filter (`Seccomp: 2`):

```
unshare CLONE_NEWNS/NEWUSER/NEWPID/NEWNET/NEWUTS/NEWIPC -> EPERM
clone   CLONE_NEWNS, CLONE_NEWUSER                      -> EPERM
```

Kernel settings were permissive (`unprivileged_userns_clone=1`,
`max_user_namespaces=2147483647`); the filter is the blocker. Every OCI runtime
(runc, crun, youki) needs at least `clone(CLONE_NEWNS)` to pivot a rootfs, so
podman, rootless Docker and nerdctl all fail identically. A remote daemon
(`DOCKER_HOST=tcp://…` or `ssh://…`) is the only container option that would
work; `Computer` now reuses its configured client everywhere so `DOCKER_HOST` is
actually honoured.

---

## 5. Configuration reference

| Setting | Where | Meaning |
|---|---|---|
| `dockerless` | `config.dockerless`, or `INFANT_DOCKERLESS=1` | Use this host as the computer |
| `INFANT_VG_URL` | env | Where the UI-TARS server listens (default `http://127.0.0.1:8888`) |
| `INFANT_NOVNC_PORT` | env | noVNC port (default 6080) |
| `INFANT_VENV` | env, `run.sh` | venv path (default `/workspace/.infant/venv`) |
| `use_oss_llm` | `config` | `True` → UI-TARS, `False` → API grounding |
| `DISPLAY` | env | The X display the agent drives (default `:10`) |

The env-driven defaults are read at **field level** in `infant/config.py`, not in
`finalize_config()`, because `backend.py` constructs its own `Config()` and never
calls `finalize_config()` — an override placed there never applies to the server.

---

## 6. Notes

`SETUP_NOTES.md` records the failures met getting this working and why each fix
is shaped the way it is — Chrome refusing to start as root, `/infant/__init__.py`
missing so every tool import failed with a misleading `NameError`, Anthropic
rejecting `temperature` together with `top_p`, the 2000 px image limit on
multi-image requests, `HF_HUB_ENABLE_HF_TRANSFER` set without the package
installed, and the disk-quota and port collisions. Read it before debugging
something that looks new.
