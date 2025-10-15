"""Unit tests for agent parser functions."""

import pytest
from unittest.mock import patch, MagicMock

from infant.agent.parser import parse, response_completion, parse_response
from infant.agent.memory.memory import (
    Memory, Analysis, Message, Task, CmdRun, IPythonRun, BrowseURL,
    Finish, TaskFinish, Classification, LocalizationFinish
)





class TestResponseCompletion:
    """Test cases for response_completion function."""

    def test_complete_bash_execute_tag(self):
        """Test completion of bash execute tag."""
        response = "Some text <execute_bash>ls -la"
        result = response_completion(response)
        assert result == "Some text <execute_bash>ls -la</execute_bash>"

    def test_complete_ipython_execute_tag(self):
        """Test completion of ipython execute tag."""
        response = "Some text <execute_ipython>print('hello')"
        result = response_completion(response)
        assert result == "Some text <execute_ipython>print('hello')</execute_ipython>"

    def test_complete_browse_tag(self):
        """Test completion of browse tag."""
        response = "Let me browse <browse>https://example.com"
        result = response_completion(response)
        assert result == "Let me browse <browse>https://example.com</browse>"

    def test_complete_task_tag(self):
        """Test completion of task tag."""
        response = "Here's the task <task>Do something important"
        result = response_completion(response)
        assert result == "Here's the task <task>Do something important</task>"

    def test_complete_analysis_tag(self):
        """Test completion of analysis tag."""
        response = "My analysis: <analysis>This is the analysis"
        result = response_completion(response)
        assert result == "My analysis: <analysis>This is the analysis</analysis>"

    def test_complete_multiple_tags(self):
        """Test completion of multiple incomplete tags."""
        response = "<execute_bash>ls -la\n<task>Do something"
        result = response_completion(response)
        assert result == "<execute_bash>ls -la\n<task>Do something</execute_bash></task>"

    def test_complete_summarize_tags(self):
        """Test completion of summarize-related tags."""
        response = "Summary: <key_steps>Step 1\n<reason>Because"
        result = response_completion(response)
        assert result == "Summary: <key_steps>Step 1\n<reason>Because</key_steps></reason>"

    def test_complete_classification_tag(self):
        """Test completion of classification tag."""
        response = "Classification: <clf_task>task1, task2"
        result = response_completion(response)
        assert result == "Classification: <clf_task>task1, task2</clf_task>"

    def test_complete_finish_tags(self):
        """Test completion of finish-related tags."""
        response = "Done <finish>Task completed\nAlso <task_finish>All done"
        result = response_completion(response)
        assert result == "Done <finish>Task completed\nAlso <task_finish>All done</finish></task_finish>"

    def test_complete_localization_finish_tag(self):
        """Test completion of localization finish tag."""
        response = "Location found <loca_finish>coordinates here"
        result = response_completion(response)
        assert result == "Location found <loca_finish>coordinates here</loca_finish>"

    def test_already_complete_tags(self):
        """Test that already complete tags are not modified."""
        response = "<execute_bash>ls -la</execute_bash>"
        result = response_completion(response)
        assert result == response

    def test_empty_response(self):
        """Test completion with empty response."""
        response = ""
        result = response_completion(response)
        assert result == ""


class TestParseResponse:
    """Test cases for parse_response function."""

    def test_parse_task_simple(self):
        """Test parsing simple task."""
        response = "I need to <task>Complete this task</task>"
        result = parse_response(response)
        
        assert isinstance(result, Task)
        assert result.task == 'Complete this task'
        assert result.target is None
        assert result.thought == 'I need to'
        assert result.source == 'assistant'

    def test_parse_task_with_target(self):
        """Test parsing task with target."""
        response = "Let me <task>Do something <target>specific target</target></task>"
        result = parse_response(response)
        
        assert isinstance(result, Task)
        assert result.task == 'Do something'
        assert result.target == 'specific target'
        assert result.thought == 'Let me'

    def test_parse_analysis(self):
        """Test parsing analysis."""
        response = "Here's my analysis: <analysis>This is the analysis content</analysis>"
        result = parse_response(response)
        
        assert isinstance(result, Analysis)
        assert result.analysis == 'This is the analysis content'
        assert result.source == 'assistant'

    def test_parse_classification(self):
        """Test parsing classification."""
        response = "Classification: <clf_task>task1, task2, task3</clf_task>"
        result = parse_response(response)
        
        assert isinstance(result, Classification)
        assert result.cmd_set == ['task1', 'task2', 'task3']
        assert result.source == 'assistant'

    def test_parse_mandatory_standards(self):
        """Test parsing mandatory standards."""
        response = "Standards: <mandatory_standards>These are the standards</mandatory_standards>"
        result = parse_response(response)
        
        assert result == 'These are the standards'

    def test_parse_ipython_basic(self):
        """Test parsing basic IPython code."""
        response = "Let me run <execute_ipython>print('hello world')</execute_ipython>"
        result = parse_response(response)
        
        assert isinstance(result, IPythonRun)
        assert result.code == "print('hello world')"
        assert result.thought == 'Let me run'
        assert result.source == 'assistant'
        assert not hasattr(result, 'special_type') or result.special_type == ''

    def test_parse_ipython_visual_grounding(self):
        """Test parsing IPython with visual grounding."""
        response = "Click here <execute_ipython>mouse_left_click(100, 200)</execute_ipython>"
        result = parse_response(response)
        
        assert isinstance(result, IPythonRun)
        assert result.code == "mouse_left_click(100, 200)"
        assert result.special_type == 'visual_grounding'

    def test_parse_ipython_web_interaction(self):
        """Test parsing IPython with web interaction."""
        response = "Open browser <execute_ipython>open_browser('chrome')</execute_ipython>"
        result = parse_response(response)
        
        assert isinstance(result, IPythonRun)
        assert result.code == "open_browser('chrome')"
        assert result.special_type == 'web_interaction'

    def test_parse_ipython_file_editing(self):
        """Test parsing IPython with file editing."""
        response = "Edit file <execute_ipython>edit_file('test.py', 'content')</execute_ipython>"
        result = parse_response(response)
        
        assert isinstance(result, IPythonRun)
        assert result.code == "edit_file('test.py', 'content')"
        assert result.special_type == 'file_editing'

    def test_parse_ipython_make_tool(self):
        """Test parsing IPython with make_new_tool."""
        response = "Create tool <execute_ipython>make_new_tool('my_tool')</execute_ipython>"
        result = parse_response(response)
        
        assert isinstance(result, IPythonRun)
        assert result.code == "make_new_tool('my_tool')"
        assert result.special_type == 'make_tool'

    def test_parse_bash_command(self):
        """Test parsing bash command."""
        response = "Run command <execute_bash>ls -la</execute_bash>"
        result = parse_response(response)
        
        assert isinstance(result, CmdRun)
        assert result.command == 'ls -la'
        assert result.thought == 'Run command'
        assert result.source == 'assistant'

    def test_parse_finish(self):
        """Test parsing finish command."""
        response = "Task completed <finish>All done</finish>"
        result = parse_response(response)
        
        assert isinstance(result, Finish)
        assert result.thought == 'Task completed'
        assert result.source == 'assistant'

    def test_parse_task_finish(self):
        """Test parsing task finish command."""
        response = "Task is done <task_finish>Completed successfully</task_finish>"
        result = parse_response(response)
        
        assert isinstance(result, TaskFinish)
        assert result.thought == 'Task is done'
        assert result.source == 'assistant'

    def test_parse_localization_finish(self):
        """Test parsing localization finish command."""
        response = "Found location <loca_finish>x=100, y=200</loca_finish>"
        result = parse_response(response)
        
        assert isinstance(result, LocalizationFinish)
        assert result.thought == 'Found location'
        assert result.coordination == 'x=100, y=200'
        assert result.source == 'assistant'

    def test_parse_browse_url(self):
        """Test parsing browse URL command."""
        response = "Let me browse <browse>https://example.com</browse>"
        result = parse_response(response)
        
        assert isinstance(result, BrowseURL)
        assert result.url == 'https://example.com'
        assert result.thought == 'Let me browse'
        assert result.source == 'assistant'

    def test_parse_message_fallback(self):
        """Test parsing falls back to Message for unrecognized content."""
        response = "This is just a regular message without any special tags."
        result = parse_response(response)
        
        assert isinstance(result, Message)
        assert result.thought == response
        assert result.source == 'assistant'

    def test_parse_multiline_content(self):
        """Test parsing with multiline content."""
        response = """Let me analyze this:
        <analysis>
        This is a multiline
        analysis with several
        lines of content
        </analysis>"""
        result = parse_response(response)
        
        assert isinstance(result, Analysis)
        assert 'multiline' in result.analysis
        assert 'several' in result.analysis

    def test_parse_empty_tags(self):
        """Test parsing with empty tags."""
        response = "Empty task <task></task>"
        result = parse_response(response)
        
        assert isinstance(result, Task)
        assert result.task == ''
        assert result.thought == 'Empty task'

    def test_parse_nested_tags_not_supported(self):
        """Test that nested tags are not properly supported."""
        response = "<task>Outer <task>Inner</task></task>"
        result = parse_response(response)
        
        # Should match the first closing tag
        assert isinstance(result, Task)
        assert result.task == 'Outer <task>Inner'


class TestParseFunction:
    """Test cases for the main parse function."""

    def test_parse_calls_completion_and_parsing(self):
        """Test that parse function calls both completion and parsing."""
        response = "Test <execute_bash>ls"
        
        with patch('infant.agent.parser.response_completion') as mock_completion:
            with patch('infant.agent.parser.parse_response') as mock_parse:
                mock_completion.return_value = "completed_response"
                mock_parse.return_value = Message(thought="test")
                
                result = parse(response)
                
                mock_completion.assert_called_once_with(response)
                mock_parse.assert_called_once_with("completed_response")

    def test_parse_integration(self):
        """Test parse function integration."""
        response = "Run command <execute_bash>echo hello"
        result = parse(response)
        
        assert isinstance(result, CmdRun)
        assert result.command == 'echo hello'
        assert result.thought == 'Run command'

    def test_parse_with_completion_needed(self):
        """Test parse function when completion is needed."""
        response = "Incomplete <task>Do something"
        result = parse(response)
        
        assert isinstance(result, Task)
        assert result.task == 'Do something'

    @patch('infant.agent.parser.logger')
    def test_parse_logging(self, mock_logger):
        """Test that parsing logs appropriate messages."""
        response = "<analysis>Test analysis</analysis>"
        result = parse(response)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert isinstance(call_args[0][0], Analysis)
        assert call_args[1]['extra']['msg_type'] == 'Analysis'


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_parse_malformed_regex(self):
        """Test parsing with content that might break regex."""
        response = "Test with [brackets] and (parentheses) and {braces}"
        result = parse_response(response)
        
        assert isinstance(result, Message)
        assert result.thought == response

    def test_parse_special_characters(self):
        """Test parsing with special characters."""
        response = "<task>Task with $pecial ch@racters & symbols!</task>"
        result = parse_response(response)
        
        assert isinstance(result, Task)
        assert result.task == "Task with $pecial ch@racters & symbols!"

    def test_parse_unicode_content(self):
        """Test parsing with unicode content."""
        response = "<analysis>分析内容 with émojis 🚀</analysis>"
        result = parse_response(response)
        
        assert isinstance(result, Analysis)
        assert "分析内容" in result.analysis
        assert "🚀" in result.analysis

    def test_parse_very_long_content(self):
        """Test parsing with very long content."""
        long_content = "x" * 10000
        response = f"<task>{long_content}</task>"
        result = parse_response(response)
        
        assert isinstance(result, Task)
        assert result.task == long_content

    def test_parse_multiple_same_tags(self):
        """Test parsing with multiple instances of same tag."""
        response = "<task>First task</task> and <task>Second task</task>"
        result = parse_response(response)
        
        # Should match the first occurrence
        assert isinstance(result, Task)
        assert result.task == "First task"