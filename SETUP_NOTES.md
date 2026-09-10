# InfantAgent — local setup notes (2026-09-10)

Environment: Linux container, 1x NVIDIA A100-80GB, Python 3.11, `uv` 0.9, no conda.

## What was done

1. **Repo**: cloned at commit `19995a3` (2025-11-10).
2. **Virtualenv**: `/workspace/.infant/venv` (**Python 3.12.3** after the 2026-09-10 rebuild; originally 3.11.13 -- `requires-python = ">=3.11"` lets uv pick the system default. Verified working, but it is not the interpreter the lockfile was first resolved against; `uv sync --python 3.11` restores the original.)
   Put on the large `/workspace` mount because `/` only has ~28 GB free and the
   dependency set (torch, vLLM, CUDA libs, easyocr, llama-index, chromadb, …) is ~17 GB.
3. **System packages**: `ffmpeg`, `libchromaprint-tools`, `libsndfile1` (via apt).
4. **Python deps**: installed from the lockfile for a reproducible, author-tested set:
   ```
   export UV_CACHE_DIR=/workspace/.infant/cache-uv
   export UV_PROJECT_ENVIRONMENT=/workspace/.infant/venv
   uv sync --frozen --no-install-project
   ```
   `uv pip check` → all 410 packages compatible.
5. **pyproject.toml fix**: dependency `fitz` → `pymupdf`.
   `fitz` on PyPI (v0.0.0) is a deactivated stub and fails to build, so the
   README's `uv pip install -e .` path is broken without this change. Original
   saved as `pyproject.toml.orig`.
   Note: the *lockfile* pins `fitz==0.0.1.dev2` (an unrelated rect-packing lib with
   no `fitz.open`). That only matters for `infant/tools/file_reader/filereader.py`,
   which runs **inside the Docker sandbox** (its image ships its own PyMuPDF), so
   the host install is unaffected.
6. **Version pinning**: installing from the unpinned `pyproject.toml` pulled
   `uvicorn 0.52` / `aiohttp 3.14`, which break `backend.py:31`
   (`TCPConnector(ssl=False)` is created at import time and newer aiohttp requires
   a running event loop). The lockfile versions (`uvicorn 0.34.2`,
   `aiohttp 3.11.18`, `fastapi 0.115.9`) work — `uv sync --frozen` installs these.

## Verified working

- `import infant`, `infant.main`, `infant.agent.agent`, `infant.computer.computer`,
  `infant.llm.*` — all import cleanly.
- `torch 2.6.0+cu124`, `torch.cuda.is_available()` → `True` (A100 visible).
- `uvicorn backend:app --port <p>` boots: `Application startup complete`,
  `GET /docs` → 200, `GET /openapi.json` → 200. (~45 s cold start: vLLM/CUDA import.)

## NOT working here — Docker

InfantAgent's agent runtime is entirely Docker-based: `infant/computer/computer.py`
calls `docker.from_env()` unconditionally and runs the sandbox as
`docker run --privileged --cap-add=SYS_ADMIN --cap-add=SYS_BOOT --userns=host
--device=/dev/tty0 ... /sbin/init` (a full systemd Ubuntu-22.04 + GNOME + xrdp +
Guacamole desktop the agent drives over SSH + RDP).

This session runs inside an **unprivileged container**:
- no `CAP_SYS_ADMIN` → cannot create mount namespaces → Docker cannot unpack image
  layers: `failed to register layer: unshare: operation not permitted`
- no `CAP_NET_ADMIN` → iptables/bridge networking fails
- user namespaces are seccomp-blocked → rootless Docker also fails

Docker CE 29.8 was installed and `dockerd` does start (with
`--iptables=false --bridge=none`), but **no container can run** — even
`docker run alpine true` fails at layer extraction. This is an environment
limitation, not fixable from inside.

## Dockerless mode (working here, added 2026-09-10)

Containers are impossible in this environment, but the *desktop* never needed
one. The agent drives the GUI with `xdotool` + PIL `ImageGrab` over a shell
(`infant/tools/computer_use/computeruse.py`); Docker only ever supplied "a
Linux box with a $DISPLAY", and RDP/Guacamole was for humans to watch. Both can
be replaced by plain user-space processes.

### Why podman/rootless Docker do NOT help

Not a privilege problem -- we are already uid 0. Namespace *syscalls* are
blocked outright by the outer container's seccomp filter (`Seccomp: 2`):

```
unshare CLONE_NEWNS/NEWUSER/NEWPID/NEWNET/NEWUTS/NEWIPC -> EPERM
clone   CLONE_NEWNS, CLONE_NEWUSER                      -> EPERM
```

Kernel settings are permissive (`unprivileged_userns_clone=1`,
`max_user_namespaces=2147483647`); the filter is the blocker. Every OCI runtime
(runc/crun/youki) needs at least `clone(CLONE_NEWNS)` to pivot a rootfs, so
podman, rootless Docker and nerdctl all fail identically. Only a remote daemon
(`DOCKER_HOST=tcp://…` / `ssh://…`) would work.

### Usage

```
./run.sh                # preflight + desktop + backend, one command
./run.sh --cli          # drive the agent from the terminal; no ports at all
./run.sh --no-vnc       # skip x11vnc/noVNC (only a human viewer needs them)
./run.sh --check        # run the checks only, start nothing
./run.sh --port 9000    # serve the backend elsewhere (default 8000)
./run.sh --no-install   # never apt-get; fail instead if something is missing
```

`run.sh` is idempotent and repairs the recurring traps below on every start:
it installs any missing host packages, adds `pip` to the venv if `uv sync` left
it out, deletes the `pathlib` backport if it came back, reaps leaked Jupyter
kernel-gateway/execute-server processes from earlier runs, brings the desktop
up, and warns (without blocking) about a missing API key or visual-grounding
server.

Equivalent by hand:

```
bash scripts/start_local_desktop.sh          # Xvfb :10 + openbox + x11vnc + noVNC
export INFANT_DOCKERLESS=1                   # or set config.dockerless = True
export DISPLAY=:10
uvicorn backend:app --log-level info
```

Watch the desktop at `http://localhost:6080/vnc.html` (map the port out if
remote). Verified end to end: `Computer.execute()`, `run_python()` through the
Jupyter kernel, `xdotool` input, `ImageGrab` screenshots, and Chrome rendering
on `:10`.

### Code changes

| File | Change |
|---|---|
| `infant/computer/local_shell.py` | New. `LocalShell(pexpect.spawn)` -- drop-in for `pxssh.pxssh` (`login`/`prompt`/`set_unique_prompt`), so `execute()` is untouched. |
| `infant/computer/computer.py` | `dockerless` branch: skips the docker client, container create/start/remove, `setup_user`, Guacamole and the GPU/Xorg step; `copy_to`/`get_pid`/`close` get local equivalents; new `setup_local_computer()`. |
| `infant/config.py` | `dockerless` flag, plumbed into `ComputerParams`; `INFANT_DOCKERLESS` env override. |
| `infant/tools/setup.sh` | `export DISPLAY=:0` -> `${DISPLAY:-:0}`. It is appended to `~/.bashrc`, and `_source_bashrc()` runs after, so the hard-coded `:0` used to blind xdotool on `:10`. No behaviour change in the container (DISPLAY=:0 there). |
| `scripts/start_local_desktop.sh` | New. Idempotent bring-up of the desktop stack. |
| `run.sh` | New. One-command launcher: preflight, desktop, backend. |
| `infant/computer/computer.py:117` | Pre-existing bug: `docker.DockerClient()` ignores `DOCKER_HOST` (unlike `from_env()`); now reuses `self.docker_client`. Matters only for remote-daemon setups. |

### Traps found along the way

- **`~/.bashrc`**: `init_plugins()` does `rm -f ~/.bashrc`. Harmless in a
  throwaway container, destructive on the host -- dockerless mode now copies it
  to `~/.bashrc.infant-backup` first.
- **The `/infant/miniforge3/bin/python` shim must be a wrapper, not a symlink.**
  Through a symlink Python finds no `pyvenv.cfg` beside argv[0] and silently
  falls back to `sys.prefix=/usr`, so setup.sh's pip installs land in the system
  python. A `#!/bin/sh exec <venv python> "$@"` wrapper keeps `sys.prefix`
  correct. (The first attempt polluted `/usr/local/lib/python3.12/dist-packages`
  with jupyterlab et al. -- harmless but untidy.)
- **`pathlib` 1.0.1 in the venv broke everything importing `pathlib`.** It is
  the Python-2 backport, pulled in by `pyxnat` via the lockfile
  (`uv.lock:5538`), and it uses `from collections import Sequence` (gone in
  3.10+). Removed from the venv; **`uv sync` will reinstall it** -- delete
  `site-packages/pathlib.py` and `pathlib-1.0.1.dist-info` again if it returns.
- **The venv had no `pip`** (`uv sync` does not install one); added via
  `python -m ensurepip`. setup.sh needs it.
- **`/infant/logs` must exist** or setup.sh's `while ! grep …` wait loop spins
  forever. Created by `setup_local_computer()`.
- Repeated `Computer()` inits leak kernel-gateway/execute-server processes;
  `pkill -f kernelgateway; pkill -f execute_server.py` between runs.

### Host packages installed

`xvfb x11vnc xdotool scrot openbox xterm novnc websockify openssh-server
x11-utils xauth`, plus Google Chrome 153 (required by `PYTHON_SETUP_CODE`,
which looks for `google-chrome-stable`).

### The venv must live in a dot-directory (learned the hard way)

`initialize_agent()` clears the sandbox workspace on every run. In a container
that is a throwaway mount; in dockerless mode it is the host's real
`/workspace`. The first dockerless backend run therefore deleted the 17 GB venv
at `/workspace/infant/venv`. `.cache` and `.git` survived only because the glob
does not match dot-entries.

The workspace path cannot simply be moved: the tools hard-code `/workspace`
(`tools/computer_use/computeruse.py` writes screenshots to
`/workspace/screenshots`), as does the sandbox <-> host path translation in
`helper_functions/` and `agent/memory/`. So the venv moved instead:

- venv now at **`/workspace/.infant/venv`** (dot-entry -> the glob misses it)
- `main.py` clears `computer.computer_workspace_dir`, not a hard-coded path,
  and refuses outright if that resolves to a system directory
  (`_PROTECTED_DIRS`)
- `Computer._assert_venv_survives_workspace_wipe()` fails at startup if the
  venv is inside the workspace without being shielded, so the invariant is
  checked rather than assumed

Recreate the venv with:

```
export UV_CACHE_DIR=/workspace/.infant/cache-uv
export UV_PROJECT_ENVIRONMENT=/workspace/.infant/venv
uv sync --frozen --no-install-project
```

### Nobody has to watch the desktop

Only a human viewer needs x11vnc/noVNC. Verified by stopping both (ports 5910
and 6080 closed) and running the agent anyway: it opened a window, found it
with `xdotool search`, clicked and typed into it, and captured a full
1920x1080 screenshot. What the agent actually needs is **Xvfb plus a window
manager** — nothing network-facing.

That matters on hosts where the ports cannot be reached from outside (this pod
exposes only SSH; RunPod's HTTP proxy 404s on undeclared ports):

```
./run.sh --no-vnc      # desktop for the agent, no viewer
./run.sh --cli         # drive the agent from the terminal, no ports at all
```

`--cli` runs `python -m infant.main`, an interactive request loop, so the whole
system works over a plain SSH session or the RunPod web terminal.

### An empty desktop looks broken

openbox with no windows renders as pure black, indistinguishable from a failed
start. `start_local_desktop.sh` now paints the root window and opens one
terminal, and it decides whether a terminal is already there by looking for a
*window* (`xdotool search`) rather than a process -- an xterm whose window has
gone lingers as a process and made the check lie.

### Running actual tasks (added 2026-09-10)

`scripts/run_task.py` runs one request non-interactively and saves everything to
`runs/<timestamp>/` (`answer.md`, `trajectory.json`, `dialogue.json`,
`summary.txt`, `screenshots/`). The repo's own `save_to_dataset()` cannot be
used: it walks up looking for a directory named `InfantAI` and raises here,
where the checkout is `InfantAgent`.

Bugs that had to be fixed before any task could complete:

| Symptom | Cause |
|---|---|
| `AuthenticationError: Missing Anthropic API Key` | No key. Now read from a gitignored `.env`, loaded by `run.sh`. |
| `` `temperature` and `top_p` cannot both be specified `` | `llm_api_base.py` passed both; Claude 4.5+ rejects that. Now drops `top_p` for Anthropic models only. |
| `'Userrequest' object has no attribute 'thought'` | `main.py` read `memory_list[-1].thought` unconditionally, so any agent error surfaced as this instead of the real one. |
| `dialogue.json` always empty | `memory_list_to_dialogue()` read `.content` on `Userrequest` (field is `.text`) and on `Message` (field is `.thought`). Userrequest is always first, so it raised every time. |
| Chrome never starts, `Chrome on 9222 didn't start in time` | "Running as root without --no-sandbox is not supported". The container sandbox ran as user `infant`; dockerless is root. Both launch sites now add `--no-sandbox` when `os.geteuid() == 0`. |

Note `Memory.__init__` sets `self.source`, but every subclass is a `@dataclass`
and so generates an `__init__` that overrides it; `source` is really assigned at
runtime by `parser.py`. `dataclasses.asdict()` therefore drops it -- the
trajectory serializer re-adds `source` and `output` explicitly.

### Visual grounding

`_ask_llm_for_coordinate()` sends one screenshot and `extract_coordinates()`
regexes `(x, y)` out of the reply, so the grounding model is swappable.
`config.use_oss_llm` now picks between them:

- **True** -> `LLM_OSS_BASED`, UI-TARS-1.5-7B on vLLM (needs a GPU)
- **False** -> `LLM_VG_API` (new), any litellm vision model, no GPU

Measured on the same 1920x1080 screenshot, locating the centre of a 364x199
window whose true centre was (1084, 739):

| model | answer | error |
|---|---|---|
| UI-TARS-1.5-7B | (1088, 719) | **20 px** |
| claude-sonnet-4-5 | (1004, 659) | 113 px |

The API model is usable for large targets and unreliable for small controls.
Its first attempt was 332 px out: Anthropic downsamples images whose long edge
exceeds 1568 px and the model answers in *that* frame, so a 1920px-wide
screenshot comes back scaled by ~0.82. `LLM_VG_API` now resizes explicitly and
maps the coordinates back, which is what brings 332 px down to 113 px.

(A "click the close button and see if the window shuts" test was attempted and
is **not** reported here: clicking the decoration's true close-button position
by hand did not close the window either, so the harness proved nothing.)

### Serving UI-TARS here

```
HF_HOME=/workspace/.infant/hf HF_HUB_DISABLE_XET=1 CUDA_VISIBLE_DEVICES=0 \
python -m vllm.entrypoints.openai.api_server \
  --model ByteDance-Seed/UI-TARS-1.5-7B --port 8889 --host 127.0.0.1 \
  --max-model-len 32768 --gpu-memory-utilization 0.85 --limit-mm-per-prompt image=4
```

Three environment traps, none of them about the model:

- **Port 8888 is taken.** It is `base_url_oss`'s default *and* JupyterLab's
  default, and this pod image runs one (pid 110). Moved to 8889;
  `base_url_oss` now honours `INFANT_VG_URL`. (`execute_server.py` also falls
  back to 8888 for both of its ports.)
- **`HF_HUB_ENABLE_HF_TRANSFER=1` with no `hf_transfer` installed.** Set by the
  pod image; every HF download fails, and transformers reports it as
  `Unrecognized model in ByteDance-Seed/UI-TARS-1.5-7B ... should have a
  model_type key`, which sends you off checking version support instead.
  `pip install hf_transfer` fixes it (the model is `qwen2_5_vl`, supported by
  the installed transformers 4.51.3 all along).
- **`Disk quota exceeded (os error 122)`** part-way through the download.
  `/workspace` is a RunPod network volume with its own quota; `df` reports the
  whole 404 TB cluster and tells you nothing. Freed 30 GB by deleting
  `.infant/cache-uv` (18 GB, only speeds up future `uv sync`) and
  `.infant/hf/xet` (12 GB, chunk cache duplicating `hf/hub`).
  `HF_HUB_DISABLE_XET=1` stops the duplicate from coming back.

### Caveat: no isolation

The agent runs as root directly on this host -- it can modify the repo, the
venv and `/workspace`. The container was the sandbox; there is none now. Fine
for local experimentation, not for untrusted tasks.

## To actually run the agent (original Docker path)

Needs a host with a working Docker daemon (or a `--privileged` container) plus an
NVIDIA GPU + nvidia-container-toolkit. Then:

```
source /workspace/.infant/venv/bin/activate      # or recreate: uv sync --frozen
cd infant/computer && docker build -t ubuntu-gnome-nomachine:latest -f Dockerfile .   # first time only
cd ../.. 
export CUDA_VISIBLE_DEVICES=0                    # for the UI-TARS visual-grounding model
uvicorn backend:app --log-level info
```

Then put your Anthropic API key in `config.toml` (or the frontend `setting` panel),
open the frontend, and follow README step 4 (Guacamole desktop setup at
`http://localhost:4443/guacamole/`).
