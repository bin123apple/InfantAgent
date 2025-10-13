import os
import asyncio, sys, textwrap

async def run_code_in_subprocess(code: str, timeout: float = 120.0, extra_env: dict | None = None):
    code = textwrap.dedent(code)
    env = os.environ.copy()
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items() if v is not None})
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-u", "-c", code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, b"", f"Execution timed out after {timeout}s".encode()
    return proc.returncode, stdout, stderr