import os
from dataclasses import dataclass

from infant.tools.requirement import PluginRequirement

@dataclass
class AdvancedtoolsRequirement(PluginRequirement):
    name: str = 'computer_use'
    host_src: str = os.path.dirname(
        os.path.abspath(__file__)
    )  # The directory of this file
    computer_dest: str = '/infant/tools/advanced_tools'