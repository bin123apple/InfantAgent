<div align="center">
<h1 align="center">
  <sub>
    <img
      src="https://raw.githubusercontent.com/bin123apple/InfantAgent/main/asset/Logo.png"
      alt="InfantAgent Logo"
      width="40"
    />
  </sub>
  InfantAgent &mdash; dockerless
</h1>
</div>

A multimodal agent that interacts with a PC the way a person does: it looks at
the screen, moves the mouse, types, and runs shell commands.

**This branch runs it without Docker.** Upstream `main` requires a privileged
container — a systemd Ubuntu image with GNOME, xrdp and Guacamole, driven over
SSH and RDP. Where containers cannot be created at all, that path is closed.

It turns out the container was never the point. The agent drives the GUI with
`xdotool` and grabs frames with PIL (`infant/tools/computer_use/computeruse.py`),
both over a shell. Docker supplied "a Linux box with a `$DISPLAY`"; RDP and
Guacamole existed so a **human** could watch. Both are replaceable with ordinary
user-space processes.

| Container provided | Dockerless replacement |
|---|---|
| A Linux box reached over SSH | A local `bash` session (`infant/computer/local_shell.py`) |
| A GNOME desktop on `$DISPLAY` | `Xvfb :10` + `openbox` |
| RDP + Guacamole for a viewer | `x11vnc` + noVNC — optional, the agent never uses it |
| UI-TARS on a GPU for grounding | UI-TARS, **or** an API vision model — no GPU |

> **This removes the sandbox.** The agent runs as your user, directly on the
> host, and can modify anything that user can. Read [§6 Isolation](#6-isolation)
> before pointing it at anything you would not run yourself.

---

## Contents

1. [Quick start](#1-quick-start)
2. [Environment](#2-environment)
3. [Configuration](#3-configuration)
4. [Running](#4-running)
5. [Visual grounding: GPU or API](#5-visual-grounding-gpu-or-api)
6. [Isolation](#6-isolation)
7. [Troubleshooting](#7-troubleshooting)
8. [Why podman / rootless Docker do not help](#8-why-podman--rootless-docker-do-not-help)

---

## 1. Quick start

The path with no GPU and no model download — grounding runs on the API:

```bash
git clone -b dockerless https://github.com/bin123apple/InfantAgent.git
cd InfantAgent

# Python environment (see §2 for why --frozen matters)
export UV_PROJECT_ENVIRONMENT=/workspace/.infant/venv   # ~20 GB, see §2
uv sync --frozen --no-install-project

# API key
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# No GPU: ground with the API vision model instead of UI-TARS
echo 'INFANT_USE_OSS_LLM=0' >> .env

./run.sh
```

`run.sh` installs the missing host packages, repairs the two known environment
traps, brings up the desktop, and starts the backend on `:8000`. Watch the agent
at `http://localhost:6080/vnc.html`; nobody has to.

If you cannot reach those ports (a pod that only exposes SSH, say):

```bash
./run.sh --cli     # interactive request loop in the terminal, no ports at all
```

---

## 2. Environment

Verified on Ubuntu 24.04, Python 3.11/3.12, `uv` 0.9. A GPU is needed **only**
if you choose to serve UI-TARS locally (§5).

### 2.1 Python environment

Install from the lockfile. Installing unpinned from `pyproject.toml` pulls
`uvicorn 0.52` / `aiohttp 3.14`, which break `backend.py` at import time
(`TCPConnector(ssl=False)` is constructed at module scope and newer aiohttp
requires a running event loop).

```bash
export UV_CACHE_DIR=/big/disk/cache-uv        # the cache reaches ~18 GB
export UV_PROJECT_ENVIRONMENT=/workspace/.infant/venv
uv sync --frozen --no-install-project
```

Two things the lockfile does not leave you with. **`run.sh` repairs both on
every start**, so you only need these if you are starting the agent by hand:

- **No `pip`.** `uv sync` does not install one, and the agent's
  `infant/tools/setup.sh` shells out to `python -m pip`.
  Fix: `python -m ensurepip --upgrade`.
- **A `pathlib` backport that breaks every import of `pathlib`.** `pyxnat`
  drags PyPI `pathlib` 1.0.1 in through the lockfile. It is the Python-2
  backport, it shadows the stdlib module on 3.10+, and it dies on
  `from collections import Sequence`. Fix: delete `site-packages/pathlib.py`
  and `site-packages/pathlib-1.0.1.dist-info`. **`uv sync` restores it**, so
  re-delete after any sync.

### 2.2 Where the venv may live

The agent **clears its workspace on every run** (`initialize_agent()` in
`infant/main.py`). The workspace is `/workspace` and cannot be moved: the tools
hard-code it (`computeruse.py` writes to `/workspace/screenshots`), as does the
sandbox↔host path translation.

So nothing else may sit in `/workspace` unprotected. The wipe is a plain
`rm -rf *`, and that glob does not match dot-entries — a venv at
`/workspace/.infant/venv` survives, one at `/workspace/infant/venv` does not.
`Computer.setup_local_computer()` asserts this at startup instead of letting you
find out afterwards. A `.gitignore` is also written into the workspace, because
`initialize_agent()` then runs `git add .`, which *does* descend into
dot-directories.

Putting the venv outside `/workspace` entirely is equally fine.

### 2.3 Host packages

```bash
apt-get install -y xvfb x11vnc xdotool scrot openbox xterm \
                   novnc websockify x11-utils xauth x11-xserver-utils
```

Google Chrome is required — `PYTHON_SETUP_CODE` looks for
`google-chrome-stable` by name:

```bash
curl -fsSLo /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y /tmp/chrome.deb
```

`./run.sh` installs everything in the first list automatically and warns (without
blocking) if Chrome is missing.

### 2.4 API key

`.env` is gitignored; `run.sh` loads it without overriding anything already
exported.

```
ANTHROPIC_API_KEY=sk-ant-...
```

Alternatively put it in `config.toml` per role, or type it into the frontend's
`setting` panel.

---

## 3. Configuration

### 3.1 Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `INFANT_DOCKERLESS` | `0` | `1` → use this host as the computer |
| `INFANT_USE_OSS_LLM` | `1` | `0` → ground with the API model, no GPU (§5) |
| `INFANT_VG_URL` | `http://127.0.0.1:8888` | Where the UI-TARS server listens |
| `INFANT_NOVNC_PORT` | `6080` | noVNC port |
| `INFANT_VENV` | `/workspace/.infant/venv` | venv path, used by `run.sh` |
| `DISPLAY` | `:10` | The X display the agent drives |
| `BACKEND_PORT` | `8000` | Backend port (or `./run.sh --port N`) |

`run.sh` sets `INFANT_DOCKERLESS=1` itself. These defaults are read at **field
level** in `infant/config.py`, not in `finalize_config()`, because `backend.py`
constructs its own `Config()` and never calls `finalize_config()` — an override
placed there never reaches the server.

### 3.2 Models

`config.toml` assigns a model per role:

```toml
[planning_llm]
model = "claude-opus-4-8"      # decomposes the task, decides the next step
[classification_llm]
model = "claude-opus-4-8"
[execution_llm]
model = "claude-opus-4-8"      # writes the actual commands
[vg_llm]
model_oss = "ByteDance-Seed/UI-TARS-1.5-7B"   # visual grounding (§5)
```

An empty `api_key` falls back to `ANTHROPIC_API_KEY`.

Note that Opus 4.7 and later **removed the sampling parameters** — `top_p` is
rejected outright, and so is any `temperature` other than the 1.0 default.
`llm_api_base.py` drops both for those models; other providers are untouched.

---

## 4. Running

```bash
./run.sh                # preflight + desktop + backend on :8000
./run.sh --cli          # terminal request loop; no ports at all
./run.sh --no-vnc       # skip x11vnc/noVNC (only a viewer needs them)
./run.sh --check        # run the checks only, start nothing
./run.sh --port 9000    # backend elsewhere
./run.sh --no-install   # never apt-get; fail if something is missing
```

`run.sh` is idempotent. Every start it: installs missing host packages, adds
`pip` to the venv, deletes the `pathlib` backport if `uv sync` brought it back,
reaps leaked Jupyter kernel-gateway/execute-server processes from earlier runs
(each `Computer()` starts a pair and never reaps them), brings the desktop up,
and warns about a missing API key or grounding server.

Then open the frontend, or watch the desktop at
`http://localhost:6080/vnc.html` — note the path; `/` answers too but the page
is `vnc.html`.

**Nobody has to watch it.** With x11vnc and noVNC stopped entirely, the agent
still opens windows, finds them with `xdotool`, clicks, types and screenshots.
Only **Xvfb plus a window manager** are required; the VNC layer is for humans.

### 4.1 One task, non-interactively

```bash
python scripts/run_task.py --task "..."             # inline
python scripts/run_task.py --task-file task.txt     # from a file
```

Writes a self-contained `runs/<timestamp>/`:

| File | Contents |
|---|---|
| `answer.md` | The agent's final answer |
| `trajectory.json` | Every memory, raw |
| `dialogue.json` | The same trajectory as a chat transcript |
| `summary.txt` | Step counts, timing, end state |
| `screenshots/` | What the agent captured |

The repo's own `save_to_dataset()` is not used: it walks up looking for a
directory named `InfantAI` and raises in a checkout named anything else.

**Copy anything you want out of `/workspace` before the next run**, which wipes
it. `scripts/traj_to_dialogue.py` rebuilds a transcript from a saved trajectory.

---

## 5. Visual grounding: GPU or API

Grounding turns "the blue OK button" into a pixel coordinate to click.
`use_oss_llm` picks the backend, and `extract_coordinates()` only regexes
`(x, y)` out of the reply — so the model is swappable.

### 5.1 API model — no GPU (recommended)

```bash
echo 'INFANT_USE_OSS_LLM=0' >> .env
./run.sh
```

That is the whole setup. It uses the same model as the other roles
(`config.toml`), needs no server, no download, and no GPU.

### 5.2 UI-TARS on a local GPU

Needs a GPU and a ~31 GB download.

```bash
HF_HOME=/big/disk/hf HF_HUB_DISABLE_XET=1 CUDA_VISIBLE_DEVICES=0 \
python -m vllm.entrypoints.openai.api_server \
  --model ByteDance-Seed/UI-TARS-1.5-7B --port 8889 --host 127.0.0.1 \
  --max-model-len 32768 --gpu-memory-utilization 0.85 --limit-mm-per-prompt image=4
```

```bash
echo 'INFANT_VG_URL=http://127.0.0.1:8889' >> .env
./run.sh
```

Mind the port: `base_url_oss` defaults to **8888, which is also JupyterLab's
default** — images that already run one (RunPod's, for instance) collide, and
vLLM fails with `OSError: [Errno 98] Address already in use`.
`HF_HUB_DISABLE_XET=1` avoids a chunk cache that duplicates the whole download.

### 5.3 Which to pick

Measured on a 1920x1080 screenshot, locating element centres — synthetic targets
down to 18x18 px, so ground truth is exact to the pixel:

| Backend | Median error | Cost | Needs |
|---|---|---|---|
| `claude-opus-4-8` (API) | **1.0 px** | ~$0.015 / call | nothing |
| UI-TARS-1.5-7B (local) | 8.5 px | free after setup | GPU + 31 GB |

The API model is both more accurate and simpler to run here. Its accuracy
depends on **not** over-shrinking the screenshot: Opus 4.7+ accepts 2576 px on
the long edge, so a 1920x1080 frame passes through untouched, while older models
cap at 1568 px — and that resampling alone cost ~100 px of accuracy in testing,
because the model answers in the coordinate space of the image it actually sees.
`LLM_VG_API` applies Anthropic's documented per-model scale formula and maps the
returned coordinates back.

UI-TARS remains the better choice if you are cost-sensitive, offline, or already
have the GPU idle. Its errors were a consistent offset rather than noise.

---

## 6. Isolation

There is none. The container was the sandbox; this mode has no replacement. The
agent runs as your user and can modify the repo, the venv, and anything else
that user can reach. Two guards exist, and they are narrow:

- `initialize_agent()` refuses to clear a workspace that resolves to a system
  directory (`_PROTECTED_DIRS` in `infant/main.py`).
- `setup_local_computer()` refuses to start if the venv sits somewhere the
  workspace wipe would reach.

Both exist because that wipe destroyed a 17 GB venv during development.

Everything else is unguarded. Chrome runs with `--no-sandbox` (it will not start
as root otherwise). `init_plugins()` overwrites `~/.bashrc` — dockerless copies
it to `~/.bashrc.infant-backup` first — and sets a **global** git identity of
`infant <infant@ai.com>`, which affects every repo on the machine.

Fine for experimenting on a machine you own. Not for untrusted tasks. Running
the agent as a dedicated unprivileged user is the obvious next step and is not
implemented here.

---

## 7. Troubleshooting

| Symptom | Cause |
|---|---|
| Desktop is pure black | An empty `openbox` root window. `start_local_desktop.sh` paints it and opens a terminal so "up" is distinguishable from "failed". |
| `NameError: BrowserConfig is not defined` | `/infant/__init__.py` missing, so the tools' absolute imports failed several layers earlier. Created by `setup_local_computer()`. |
| `Chrome on 9222 didn't start in time` | Chrome will not run as root without `--no-sandbox`. Added automatically when euid is 0. |
| `image dimensions exceed max allowed size ... 2000 pixels` | A full-page browser screenshot in a multi-image request. Images are downscaled to 1568 px before sending. |
| `` `temperature` and `top_p` cannot both be specified `` | Claude 4.5+. Both are dropped for models that removed them. |
| `Unrecognized model in <a real model>` | `HF_HUB_ENABLE_HF_TRANSFER=1` set without `hf_transfer` installed — every HF download fails and transformers reports it as an unknown model. `pip install hf_transfer`. |
| `Disk quota exceeded (os error 122)` | A network volume with its own quota; `df` reports the whole cluster and tells you nothing. |
| `dialogue.json` is empty | Fixed on this branch — `memory_list_to_dialogue()` read the wrong field on the first memory and raised every time. |
| Browser keeps timing out on one site | Some sites (Akamai bot protection) reset `curl`/`wget` while Chrome gets through. Navigate with the browser rather than guessing download URLs. |

`SETUP_NOTES.md` records how each of these was found and why the fix is shaped
the way it is.

---

## 8. Why podman / rootless Docker do not help

Not a privilege problem — the failing host was already uid 0. Namespace
*syscalls* are blocked by the outer container's seccomp filter (`Seccomp: 2`):

```
unshare CLONE_NEWNS/NEWUSER/NEWPID/NEWNET/NEWUTS/NEWIPC -> EPERM
clone   CLONE_NEWNS, CLONE_NEWUSER                      -> EPERM
```

Kernel settings were permissive (`unprivileged_userns_clone=1`,
`max_user_namespaces=2147483647`); the filter is the blocker. Every OCI runtime
(runc, crun, youki) needs at least `clone(CLONE_NEWNS)` to pivot a rootfs, so
podman, rootless Docker and nerdctl all fail identically.

A remote daemon is the one container option that would work — and `Computer` now
reuses its configured client everywhere, so `DOCKER_HOST=tcp://…` / `ssh://…` is
actually honoured (a bare `docker.DockerClient()` in one place used to ignore
it). Note that with a remote daemon the volume mounts and `ssh_hostname` refer to
that machine, and the Guacamole URL is hard-coded to localhost.

---

## Upstream

For the original Docker-based instructions, the paper, and the project itself,
see [`main`](https://github.com/bin123apple/InfantAgent) and
[the Discord](https://discord.gg/urxApEGcwV).
