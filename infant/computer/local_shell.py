"""Local shell transport, a drop-in replacement for `pxssh.pxssh`.

InfantAgent normally drives its sandbox over SSH into a Docker container.  On
hosts where containers cannot be created (no CAP_SYS_ADMIN / namespaces blocked
by seccomp) the desktop is instead run directly on the host as Xvfb + a window
manager, and there is nothing to SSH into -- the target machine *is* this
machine.

`Computer` only ever uses seven methods of the pxssh object (`login`, `prompt`,
`sendline`, `send`, `sendintr`, `expect`, `before`); all but `login` and
`prompt` already come from `pexpect.spawn`.  So a small subclass that spawns a
local bash and reproduces pxssh's unique-prompt handling is enough to keep
`Computer.execute()` and everything built on it working unchanged.
"""

import os

import pexpect

from infant.util.logger import infant_logger as logger


class LocalShell(pexpect.spawn):
    """A local bash session that quacks like `pxssh.pxssh`."""

    # Identical to pxssh's, so `execute()`'s output slicing behaves the same.
    PROMPT = r'\[PEXPECT\][\$\#] '
    PROMPT_SET_SH = r"PS1='[PEXPECT]\$ '"

    def __init__(
        self,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 120,
        encoding: str = 'utf-8',
        codec_errors: str = 'replace',
        echo: bool = False,
    ):
        shell_env = os.environ.copy()
        if env:
            shell_env.update(env)

        # A wide window keeps bash from hard-wrapping long commands, which would
        # otherwise show up inside `before` and corrupt the captured output.
        super().__init__(
            '/bin/bash',
            ['--norc', '--noprofile', '-i'],
            cwd=cwd,
            env=shell_env,
            timeout=timeout,
            encoding=encoding,
            codec_errors=codec_errors,
            echo=echo,
            dimensions=(40, 512),
        )

    def login(self, *args, **kwargs) -> bool:
        """No-op stand-in for `pxssh.login()`; just arms the unique prompt.

        Accepts and ignores pxssh's (server, username, password, port=...) so
        the caller does not have to special-case us.
        """
        self.set_unique_prompt()
        return True

    def set_unique_prompt(self) -> bool:
        self.setecho(False)
        # Drain the shell's initial prompt before replacing it.
        self.sendline('unset PROMPT_COMMAND')
        self.sendline(self.PROMPT_SET_SH)
        i = self.expect([pexpect.TIMEOUT, self.PROMPT], timeout=10)
        if i == 0:
            logger.warning('LocalShell: timed out waiting for the unique prompt')
            return False
        return True

    def prompt(self, timeout: int = -1) -> bool:
        if timeout == -1:
            timeout = self.timeout
        i = self.expect([self.PROMPT, pexpect.TIMEOUT], timeout=timeout)
        return i == 0

    def logout(self) -> None:
        try:
            self.sendline('exit')
            self.expect(pexpect.EOF, timeout=5)
        except Exception:
            pass
        finally:
            self.close(force=True)
