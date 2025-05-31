import asyncio
from dataclasses import dataclass, field
from infant.util.metrics import Metrics
from infant.agent.state.agent_state import AgentState

RESUMABLE_STATES = [
    AgentState.RUNNING,
    AgentState.PAUSED,
    AgentState.AWAITING_USER_INPUT,
    AgentState.FINISHED,
]


@dataclass
class State:
    iteration: int = 0
    max_iterations: int = 100
    num_of_chars: int = 0
    memory_queue: asyncio.Queue = asyncio.Queue()
    #background_commands_obs: list[CmdOutputObservation] = field(default_factory=list)
    memory_list: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    error: str | None = None
    agent_state: AgentState = AgentState.LOADING
    resume_state: AgentState | None = None
    metrics: Metrics = Metrics()
    delegate_level: int = 0
    steps: list | None = None
    current_step: int | None = None
    step_iteration: int | None = None
    max_step_iterations: int = 15
    last_executed_py_file: str | None = None
    execution_trace: list | None = None
    evaluation: bool = False # whether the agent is in evaluation mode
    evaluation_result: bool = True # whether the evaluation is successful
    last_task_summary: str | None = None
    brainless_mode: bool = True
    finished: bool = False # whether the agent has finished the task
    final_git_diff: str | None = None
    critic: bool = False
    critic_result: bool = True
    verify_step_by_step: bool = False # Care! This will be expensive!
    continuous_errors: int = 0 # Avoid infinite errors
    pending_user_response = None

    def reset(self):
        self.iteration: int = 0
        self.num_of_chars: int = 0
        self.delegate_level: int = 0
        self.steps: list | None = None
        self.current_step: int | None = None
        self.step_iteration: int | None = None
        self.max_step_iterations: int = 15
        self.last_executed_py_file: str | None = None
        self.execution_trace: list | None = None
        self.evaluation: bool = False # whether the agent is in evaluation mode
        self.evaluation_result: bool = True # whether the evaluation is successful
        self.last_task_summary: str | None = None
        self.brainless_mode: bool = True
        self.finished: bool = False # whether the agent has finished the task
        self.final_git_diff: str | None = None
        self.memory_list = []
        self.critic: bool = False
        self.critic_result: bool = True
        self.continuous_errors: int = 0
        self.pending_user_response = None