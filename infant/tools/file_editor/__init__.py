import os
from dataclasses import dataclass

from infant.tools.requirement import PluginRequirement

@dataclass
class FileEditorRequirement(PluginRequirement):
    name: str = 'file_editor'
    host_src: str = os.path.dirname(
        os.path.abspath(__file__)
    )  # The directory of this file
    computer_dest: str = '/infant/tools/file_editor'