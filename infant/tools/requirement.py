from dataclasses import dataclass


@dataclass
class PluginRequirement:
    """Requirement for a plugin."""

    name: str
    # FOLDER/FILES to be copied to the computer
    host_src: str
    computer_dest: str
    # NOTE: bash_script_path should be relative to the `computer_dest` path
    # bash_script_path: str
