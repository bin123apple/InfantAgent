import os
from dataclasses import dataclass

from infant.tools.requirement import PluginRequirement

@dataclass
class WebBrowserRequirement(PluginRequirement):
    name: str = 'web_browser'
    host_src: str = os.path.dirname(
        os.path.abspath(__file__)
    )  # The directory of this file
    computer_dest: str = '/infant/tools/web_browser'
