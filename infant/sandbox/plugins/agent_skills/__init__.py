import os
from dataclasses import dataclass

from infant.sandbox.plugins.agent_skills.agentskills import DOCUMENTATION
from infant.sandbox.plugins.requirement import PluginRequirement

@dataclass
class AgentSkillsRequirement(PluginRequirement):
    name: str = 'agent_skills'
    host_src: str = os.path.dirname(
        os.path.abspath(__file__)
    )  # The directory of this file
    sandbox_dest: str = '/infant/plugins/agent_skills'
    bash_script_path: str = 'setup.sh'
    documentation: str = DOCUMENTATION
