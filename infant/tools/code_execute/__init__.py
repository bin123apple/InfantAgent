import os
from dataclasses import dataclass

from infant.tools.requirement import PluginRequirement


@dataclass
class JupyterRequirement(PluginRequirement):
    name: str = 'jupyter'
    host_src: str = os.path.dirname(
        os.path.abspath(__file__)
    )  # The directory of this file
    computer_dest: str = '/infant/plugins/jupyter'
    bash_script_path: str = 'setup.sh'
