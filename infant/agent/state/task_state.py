from infant.util.exceptions import (
    TaskInvalidStateError,
)
from infant.util.logger import infant_logger as logger

OPEN_STATE = 'open'
COMPLETED_STATE = 'completed'
ABANDONED_STATE = 'abandoned'
IN_PROGRESS_STATE = 'in_progress'
VERIFIED_STATE = 'verified'
STATES = [
    OPEN_STATE,
    COMPLETED_STATE,
    ABANDONED_STATE,
    IN_PROGRESS_STATE,
    VERIFIED_STATE,
]


class Task:
    id: str
    goal: str
    parent: 'Task | None'
    subtasks: list['Task']

    def __init__(
        self,
        parent: 'Task',
        goal: str,
        state: str = OPEN_STATE,
        subtasks: list = [],  # noqa: B006
    ):
        """Initializes a new instance of the Task class.

        Args:
            parent: The parent task, or None if it is the root task.
            goal: The goal of the task.
            state: The initial state of the task.
            subtasks: A list of subtasks associated with this task.
        """
        if parent.id:
            self.id = parent.id + '.' + str(len(parent.subtasks))
        else:
            self.id = str(len(parent.subtasks))
        self.parent = parent
        self.goal = goal
        logger.debug('Creating task {self.id} with parent={parent.id}, goal={goal}')
        self.subtasks = []
        for subtask in subtasks or []:
            if isinstance(subtask, Task):
                self.subtasks.append(subtask)
            else:
                goal = subtask.get('goal')
                state = subtask.get('state')
                subtasks = subtask.get('subtasks')
                logger.debug('Reading: {goal}, {state}, {subtasks}')
                self.subtasks.append(Task(self, goal, state, subtasks))

        self.state = OPEN_STATE

    def to_string(self, indent=''):
        """Returns a string representation of the task and its subtasks.

        Args:
            indent: The indentation string for formatting the output.

        Returns:
            A string representation of the task and its subtasks.
        """
        emoji = ''
        if self.state == VERIFIED_STATE:
            emoji = '✅'
        elif self.state == COMPLETED_STATE:
            emoji = '🟢'
        elif self.state == ABANDONED_STATE:
            emoji = '❌'
        elif self.state == IN_PROGRESS_STATE:
            emoji = '💪'
        elif self.state == OPEN_STATE:
            emoji = '🔵'
        result = indent + emoji + ' ' + self.id + ' ' + self.goal + '\n'
        for subtask in self.subtasks:
            result += subtask.to_string(indent + '    ')
        return result

    def to_dict(self):
        """Returns a dictionary representation of the task.

        Returns:
            A dictionary containing the task's attributes.
        """
        return {
            'id': self.id,
            'goal': self.goal,
            'state': self.state,
            'subtasks': [t.to_dict() for t in self.subtasks],
        }

    def set_state(self, state):
        """Sets the state of the task and its subtasks.

        Args:            state: The new state of the task.

        Raises:
            TaskInvalidStateError: If the provided state is invalid.
        """
        if state not in STATES:
            logger.error('Invalid state: %s', state)
            raise TaskInvalidStateError(state)
        self.state = state
        if (
            state == COMPLETED_STATE
            or state == ABANDONED_STATE
            or state == VERIFIED_STATE
        ):
            for subtask in self.subtasks:
                if subtask.state != ABANDONED_STATE:
                    subtask.set_state(state)
        elif state == IN_PROGRESS_STATE:
            if self.parent is not None:
                self.parent.set_state(state)

    def get_current_task(self) -> 'Task | None':
        """Retrieves the current task in progress.

        Returns:
            The current task in progress, or None if no task is in progress.
        """
        for subtask in self.subtasks:
            if subtask.state == IN_PROGRESS_STATE:
                return subtask.get_current_task()
        if self.state == IN_PROGRESS_STATE:
            return self
        return None

