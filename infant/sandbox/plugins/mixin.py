import os
from typing import Protocol

from infant.util.logger import infant_logger as logger
from infant.sandbox.plugins.requirement import PluginRequirement


class SandboxProtocol(Protocol):
    # https://stackoverflow.com/questions/51930339/how-do-i-correctly-add-type-hints-to-mixin-classes

    @property
    def initialize_plugins(self) -> bool: ...

    def execute(
            self, cmd: str, stream: bool = False
    ) -> tuple[int, str]: ...

    def copy_to(self, host_src: str, sandbox_dest: str, recursive: bool = False): ...


def _source_bashrc(sandbox: SandboxProtocol):
    exit_code, output = sandbox.execute('source /infant/bash.bashrc && source ~/.bashrc')
    if exit_code != 0:
        raise RuntimeError(
            f'Failed to source /infant/bash.bashrc and ~/.bashrc with exit code {exit_code} and output: {output}'
        )
    logger.info('Sourced /infant/bash.bashrc and ~/.bashrc successfully')


class PluginMixin:
    """Mixin for Sandbox to support plugins."""

    def init_plugins(self: SandboxProtocol, requirements: list[PluginRequirement]):
        """Load a plugin into the sandbox."""

        if hasattr(self, 'plugin_initialized') and self.plugin_initialized:
            return

        if self.initialize_plugins:
            logger.info('Initializing plugins in the sandbox')

            # clean-up ~/.bashrc and touch ~/.bashrc
            exit_code, output = self.execute('rm -f ~/.bashrc && touch ~/.bashrc')

            for requirement in requirements:
                # source bashrc file when plugin loads
                _source_bashrc(self)

                # copy over the files
                self.copy_to(
                    requirement.host_src, requirement.sandbox_dest, recursive=True
                )
                logger.info(
                    f'Copied files from [{requirement.host_src}] to [{requirement.sandbox_dest}] inside sandbox.'
                )

                # Execute the bash script
                abs_path_to_bash_script = os.path.join(
                    requirement.sandbox_dest, requirement.bash_script_path
                )
                logger.info(
                    f'Initializing plugin [{requirement.name}] by executing [{abs_path_to_bash_script}] in the sandbox.'
                )
                exit_code, output = self.execute(abs_path_to_bash_script, stream=True)
                if isinstance(output, CancellableStream):
                    total_output = ''
                    for line in output:
                        if line.endswith('\n'):
                            line = line[:-1]
                        logger.debug(line)
                        total_output += line
                    _exit_code = output.exit_code()
                    output.close()
                    if _exit_code != 0:
                        raise RuntimeError(
                            f'Failed to initialize plugin {requirement.name} with exit code {_exit_code} and output: {total_output}'
                        )
                    logger.info(f'Plugin {requirement.name} initialized successfully')
                else:
                    if exit_code != 0:
                        raise RuntimeError(
                            f'Failed to initialize plugin {requirement.name} with exit code {exit_code} and output: {output}'
                        )
                    logger.info(f'Plugin {requirement.name} initialized successfully.')
        else:
            logger.info('Skipping plugin initialization in the sandbox')

        if len(requirements) > 0:
            _source_bashrc(self)

        self.plugin_initialized = True
