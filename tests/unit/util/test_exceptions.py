"""Unit tests for custom exceptions."""

import pytest

from infant.util.exceptions import (
    MaxCharsExceedError,
    AgentNoInstructionError,
    AgentEventTypeError,
    AgentAlreadyRegisteredError,
    AgentNotRegisteredError,
    ComputerInvalidBackgroundCommandError,
    TaskInvalidStateError,
    BrowserInitException,
    BrowserUnavailableException,
    LLMMalformedActionError,
    LLMNoActionError,
    LLMResponseError,
)


class TestCustomExceptions:
    """Test cases for custom exception classes."""

    def test_max_chars_exceed_error_with_params(self):
        """Test MaxCharsExceedError with parameters."""
        error = MaxCharsExceedError(num_of_chars=1000, max_chars_limit=500)
        expected_message = 'Number of characters 1000 exceeds MAX_CHARS limit: 500'
        assert str(error) == expected_message

    def test_max_chars_exceed_error_without_params(self):
        """Test MaxCharsExceedError without parameters."""
        error = MaxCharsExceedError()
        expected_message = 'Number of characters exceeds MAX_CHARS limit'
        assert str(error) == expected_message

    def test_max_chars_exceed_error_partial_params(self):
        """Test MaxCharsExceedError with partial parameters."""
        error = MaxCharsExceedError(num_of_chars=1000)
        expected_message = 'Number of characters exceeds MAX_CHARS limit'
        assert str(error) == expected_message

    def test_max_chars_exceed_error_inheritance(self):
        """Test MaxCharsExceedError inherits from Exception."""
        error = MaxCharsExceedError()
        assert isinstance(error, Exception)

    def test_agent_no_instruction_error_default(self):
        """Test AgentNoInstructionError with default message."""
        error = AgentNoInstructionError()
        assert str(error) == 'Instruction must be provided'

    def test_agent_no_instruction_error_custom(self):
        """Test AgentNoInstructionError with custom message."""
        custom_message = 'Custom instruction error'
        error = AgentNoInstructionError(custom_message)
        assert str(error) == custom_message

    def test_agent_event_type_error_default(self):
        """Test AgentEventTypeError with default message."""
        error = AgentEventTypeError()
        assert str(error) == 'Event must be a dictionary'

    def test_agent_event_type_error_custom(self):
        """Test AgentEventTypeError with custom message."""
        custom_message = 'Custom event type error'
        error = AgentEventTypeError(custom_message)
        assert str(error) == custom_message

    def test_agent_already_registered_error_with_name(self):
        """Test AgentAlreadyRegisteredError with agent name."""
        error = AgentAlreadyRegisteredError(name='TestAgent')
        expected_message = "Agent class already registered under 'TestAgent'"
        assert str(error) == expected_message

    def test_agent_already_registered_error_without_name(self):
        """Test AgentAlreadyRegisteredError without agent name."""
        error = AgentAlreadyRegisteredError()
        expected_message = 'Agent class already registered'
        assert str(error) == expected_message

    def test_agent_not_registered_error_with_name(self):
        """Test AgentNotRegisteredError with agent name."""
        error = AgentNotRegisteredError(name='UnknownAgent')
        expected_message = "No agent class registered under 'UnknownAgent'"
        assert str(error) == expected_message

    def test_agent_not_registered_error_without_name(self):
        """Test AgentNotRegisteredError without agent name."""
        error = AgentNotRegisteredError()
        expected_message = 'No agent class registered'
        assert str(error) == expected_message

    def test_computer_invalid_background_command_error_with_id(self):
        """Test ComputerInvalidBackgroundCommandError with command ID."""
        error = ComputerInvalidBackgroundCommandError(id='cmd123')
        expected_message = 'Invalid background command id cmd123'
        assert str(error) == expected_message

    def test_computer_invalid_background_command_error_without_id(self):
        """Test ComputerInvalidBackgroundCommandError without command ID."""
        error = ComputerInvalidBackgroundCommandError()
        expected_message = 'Invalid background command id'
        assert str(error) == expected_message

    def test_task_invalid_state_error_with_state(self):
        """Test TaskInvalidStateError with state."""
        error = TaskInvalidStateError(state='invalid_state')
        expected_message = 'Invalid state invalid_state'
        assert str(error) == expected_message

    def test_task_invalid_state_error_without_state(self):
        """Test TaskInvalidStateError without state."""
        error = TaskInvalidStateError()
        expected_message = 'Invalid state'
        assert str(error) == expected_message

    def test_browser_init_exception_default(self):
        """Test BrowserInitException with default message."""
        error = BrowserInitException()
        expected_message = 'Failed to initialize browser environment'
        assert str(error) == expected_message

    def test_browser_init_exception_custom(self):
        """Test BrowserInitException with custom message."""
        custom_message = 'Custom browser init error'
        error = BrowserInitException(custom_message)
        assert str(error) == custom_message

    def test_browser_unavailable_exception_default(self):
        """Test BrowserUnavailableException with default message."""
        error = BrowserUnavailableException()
        expected_message = 'Browser environment is not available, please check if has been initialized'
        assert str(error) == expected_message

    def test_browser_unavailable_exception_custom(self):
        """Test BrowserUnavailableException with custom message."""
        custom_message = 'Custom browser unavailable error'
        error = BrowserUnavailableException(custom_message)
        assert str(error) == custom_message

    def test_llm_malformed_action_error_default(self):
        """Test LLMMalformedActionError with default message."""
        error = LLMMalformedActionError()
        expected_message = 'Malformed response'
        assert str(error) == expected_message

    def test_llm_malformed_action_error_custom(self):
        """Test LLMMalformedActionError with custom message."""
        custom_message = 'Custom malformed action error'
        error = LLMMalformedActionError(custom_message)
        assert str(error) == custom_message

    def test_llm_no_action_error_default(self):
        """Test LLMNoActionError with default message."""
        error = LLMNoActionError()
        expected_message = 'Agent must return an action'
        assert str(error) == expected_message

    def test_llm_no_action_error_custom(self):
        """Test LLMNoActionError with custom message."""
        custom_message = 'Custom no action error'
        error = LLMNoActionError(custom_message)
        assert str(error) == custom_message

    def test_llm_response_error_default(self):
        """Test LLMResponseError with default message."""
        error = LLMResponseError()
        expected_message = 'Failed to retrieve action from LLM response'
        assert str(error) == expected_message

    def test_llm_response_error_custom(self):
        """Test LLMResponseError with custom message."""
        custom_message = 'Custom response error'
        error = LLMResponseError(custom_message)
        assert str(error) == custom_message

    def test_all_exceptions_inherit_from_exception(self):
        """Test that all custom exceptions inherit from Exception."""
        exception_classes = [
            MaxCharsExceedError,
            AgentNoInstructionError,
            AgentEventTypeError,
            AgentAlreadyRegisteredError,
            AgentNotRegisteredError,
            ComputerInvalidBackgroundCommandError,
            TaskInvalidStateError,
            BrowserInitException,
            BrowserUnavailableException,
            LLMMalformedActionError,
            LLMNoActionError,
            LLMResponseError,
        ]
        
        for exception_class in exception_classes:
            error = exception_class()
            assert isinstance(error, Exception)

    def test_exceptions_can_be_raised_and_caught(self):
        """Test that exceptions can be raised and caught properly."""
        with pytest.raises(MaxCharsExceedError):
            raise MaxCharsExceedError(1000, 500)

        with pytest.raises(AgentNoInstructionError):
            raise AgentNoInstructionError()

        with pytest.raises(LLMResponseError):
            raise LLMResponseError('Test error')

    def test_exception_messages_are_strings(self):
        """Test that all exception messages are strings."""
        exceptions = [
            MaxCharsExceedError(),
            MaxCharsExceedError(1000, 500),
            AgentNoInstructionError(),
            AgentEventTypeError(),
            AgentAlreadyRegisteredError('TestAgent'),
            AgentNotRegisteredError('UnknownAgent'),
            ComputerInvalidBackgroundCommandError('cmd123'),
            TaskInvalidStateError('invalid'),
            BrowserInitException(),
            BrowserUnavailableException(),
            LLMMalformedActionError(),
            LLMNoActionError(),
            LLMResponseError(),
        ]
        
        for exception in exceptions:
            assert isinstance(str(exception), str)
            assert len(str(exception)) > 0

    def test_exception_repr(self):
        """Test exception repr methods."""
        error = MaxCharsExceedError(1000, 500)
        repr_str = repr(error)
        assert 'MaxCharsExceedError' in repr_str
        assert '1000 exceeds MAX_CHARS limit: 500' in repr_str