import os
from typing import Protocol

from infant.util.logger import infant_logger as logger
from infant.tools.requirement import PluginRequirement


class ComputerProtocol(Protocol):
    # https://stackoverflow.com/questions/51930339/how-do-i-correctly-add-type-hints-to-mixin-classes

    @property
    def initialize_plugins(self) -> bool: ...

    def execute(
            self, cmd: str, stream: bool = False
    ) -> tuple[int, str]: ...

    def copy_to(self, host_src: str, computer_dest: str, recursive: bool = False): ...


def _source_bashrc(computer: ComputerProtocol):
    exit_code, output = computer.execute('source /infant/bash.bashrc && source ~/.bashrc')
    if exit_code != 0:
        raise RuntimeError(
            f'Failed to source /infant/bash.bashrc and ~/.bashrc with exit code {exit_code} and output: {output}'
        )
    logger.info('Sourced /infant/bash.bashrc and ~/.bashrc successfully')


class PluginMixin:
    """Mixin for Computer to support plugins."""

    def init_plugins(self: ComputerProtocol, requirements: list[PluginRequirement]):
        """Load a plugin into the computer."""

        if hasattr(self, 'plugin_initialized') and self.plugin_initialized:
            return

        if self.initialize_plugins:
            logger.info('Initializing plugins in the computer')

            # clean-up ~/.bashrc and touch ~/.bashrc
            exit_code, output = self.execute('rm -f ~/.bashrc && touch ~/.bashrc')

            for requirement in requirements:
                # source bashrc file when plugin loads
                _source_bashrc(self)

                # copy over the files
                self.copy_to(
                    requirement.host_src, requirement.computer_dest, recursive=True
                )
                logger.info(
                    f'Copied files from [{requirement.host_src}] to [{requirement.computer_dest}] inside computer.'
                )

                # Execute the bash script
                abs_path_to_bash_script = os.path.join(
                    requirement.computer_dest, requirement.bash_script_path
                )
                logger.info(
                    f'Initializing plugin [{requirement.name}] by executing [{abs_path_to_bash_script}] in the computer.'
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
            logger.info('Skipping plugin initialization in the computer')

        if len(requirements) > 0:
            _source_bashrc(self)

        self.plugin_initialized = True
