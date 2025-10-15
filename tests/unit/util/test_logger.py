"""Unit tests for logger utilities."""

import logging
import os
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch, mock_open

import pytest

from infant.util.logger import (
    NoColorFormatter,
    ColoredFormatter,
    RollingLogger,
    SensitiveDataFilter,
    LlmFileHandler,
    strip_ansi,
    get_console_handler,
    get_file_handler,
    log_uncaught_exceptions,
    reset_logger_for_multiprocessing,
    LOG_COLORS,
)


class TestLoggerUtilities:
    """Test cases for logger utility functions and classes."""

    def test_strip_ansi_with_color_codes(self):
        """Test strip_ansi removes ANSI color codes."""
        colored_text = '\x1B[31mRed text\x1B[0m'
        result = strip_ansi(colored_text)
        assert result == 'Red text'

    def test_strip_ansi_without_color_codes(self):
        """Test strip_ansi with plain text."""
        plain_text = 'Plain text'
        result = strip_ansi(plain_text)
        assert result == 'Plain text'

    def test_strip_ansi_complex_codes(self):
        """Test strip_ansi with complex ANSI codes."""
        complex_text = '\x1B[31;1mBold red\x1B[0m and \x1B[32;4mUnderlined green\x1B[0m'
        result = strip_ansi(complex_text)
        assert result == 'Bold red and Underlined green'

    def test_no_color_formatter(self):
        """Test NoColorFormatter strips ANSI codes."""
        formatter = NoColorFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='\x1B[31mColored message\x1B[0m',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert '\x1B[31m' not in formatted
        assert '\x1B[0m' not in formatted
        assert 'Colored message' in formatted

    def test_colored_formatter_with_msg_type(self):
        """Test ColoredFormatter with msg_type."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.msg_type = 'ERROR'
        
        with patch('infant.util.logger.DISABLE_COLOR_PRINTING', False):
            formatted = formatter.format(record)
            assert 'ERROR' in formatted
            assert 'Test message' in formatted

    def test_colored_formatter_with_event_source(self):
        """Test ColoredFormatter with event_source."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.msg_type = 'Request'
        record.event_source = 'User'
        
        with patch('infant.util.logger.DISABLE_COLOR_PRINTING', False):
            formatted = formatter.format(record)
            assert 'Test message' in formatted

    def test_colored_formatter_step_type(self):
        """Test ColoredFormatter with STEP msg_type."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Step message',
            args=(),
            exc_info=None
        )
        record.msg_type = 'STEP'
        
        with patch('infant.util.logger.LOG_ALL_EVENTS', True):
            formatted = formatter.format(record)
            assert 'Step message' in formatted
            assert '==============' in formatted

    def test_rolling_logger_init(self):
        """Test RollingLogger initialization."""
        logger = RollingLogger(max_lines=5, char_limit=50)
        assert logger.max_lines == 5
        assert logger.char_limit == 50
        assert len(logger.log_lines) == 5
        assert all(line == '' for line in logger.log_lines)

    @patch('sys.stdout.isatty')
    def test_rolling_logger_is_enabled(self, mock_isatty):
        """Test RollingLogger is_enabled method."""
        logger = RollingLogger()
        
        with patch('infant.util.logger.DEBUG', True):
            mock_isatty.return_value = True
            assert logger.is_enabled() is True
            
            mock_isatty.return_value = False
            assert logger.is_enabled() is False

    @patch('sys.stdout')
    def test_rolling_logger_write_methods(self, mock_stdout):
        """Test RollingLogger write methods."""
        logger = RollingLogger()
        
        with patch.object(logger, 'is_enabled', return_value=True):
            logger._write('test')
            mock_stdout.write.assert_called_with('test')
            
            logger._flush()
            mock_stdout.flush.assert_called()

    def test_rolling_logger_add_line(self):
        """Test RollingLogger add_line method."""
        logger = RollingLogger(max_lines=3, char_limit=10)
        
        with patch.object(logger, 'print_lines'):
            logger.add_line('first line')
            assert logger.log_lines[-1] == 'first line'
            
            logger.add_line('second line that is too long')
            assert logger.log_lines[-1] == 'second lin'  # truncated

    def test_sensitive_data_filter(self):
        """Test SensitiveDataFilter masks sensitive information."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg="api_key='secret123' and aws_access_key_id='AKIA123'",
            args=(),
            exc_info=None
        )
        
        result = filter_obj.filter(record)
        assert result is True
        assert 'secret123' not in record.msg
        assert 'AKIA123' not in record.msg
        assert "api_key='******'" in record.msg
        assert "aws_access_key_id='******'" in record.msg

    def test_sensitive_data_filter_env_vars(self):
        """Test SensitiveDataFilter masks environment variables."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg="LLM_API_KEY='sk-123' and GITHUB_TOKEN='ghp_456'",
            args=(),
            exc_info=None
        )
        
        result = filter_obj.filter(record)
        assert result is True
        assert 'sk-123' not in record.msg
        assert 'ghp_456' not in record.msg
        assert "LLM_API_KEY='******'" in record.msg
        assert "GITHUB_TOKEN='******'" in record.msg

    def test_get_console_handler(self):
        """Test get_console_handler creates proper handler."""
        handler = get_console_handler(logging.DEBUG, 'test_info')
        
        assert isinstance(handler, logging.StreamHandler)
        assert handler.level == logging.DEBUG
        assert isinstance(handler.formatter, ColoredFormatter)

    def test_get_file_handler(self, temp_dir):
        """Test get_file_handler creates proper handler."""
        handler = get_file_handler(temp_dir, logging.INFO)
        
        assert isinstance(handler, logging.FileHandler)
        assert handler.level == logging.INFO
        assert temp_dir in handler.baseFilename
        assert 'infant_' in handler.baseFilename
        assert '.log' in handler.baseFilename

    def test_log_uncaught_exceptions(self, caplog):
        """Test log_uncaught_exceptions logs properly."""
        try:
            raise ValueError('Test exception')
        except ValueError:
            import sys
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            with caplog.at_level(logging.ERROR):
                log_uncaught_exceptions(exc_type, exc_value, exc_traceback)
            
            assert 'Test exception' in caplog.text
            assert 'ValueError' in caplog.text

    def test_llm_file_handler_init(self, temp_dir):
        """Test LlmFileHandler initialization."""
        with patch('infant.util.logger.LOG_DIR', temp_dir):
            with patch('infant.util.logger.DEBUG', True):
                handler = LlmFileHandler('test_prompt')
                
                assert handler.filename == 'test_prompt'
                assert handler.message_counter == 1
                assert os.path.exists(handler.log_directory)

    def test_llm_file_handler_emit(self, temp_dir):
        """Test LlmFileHandler emit method."""
        with patch('infant.util.logger.LOG_DIR', temp_dir):
            with patch('infant.util.logger.DEBUG', False):
                handler = LlmFileHandler('test_prompt')
                record = logging.LogRecord(
                    name='test',
                    level=logging.INFO,
                    pathname='',
                    lineno=0,
                    msg='Test log message',
                    args=(),
                    exc_info=None
                )
                
                handler.emit(record)
                
                # Check that file was created and message counter incremented
                assert handler.message_counter == 2
                log_files = os.listdir(handler.log_directory)
                assert any('test_prompt_001.log' in f for f in log_files)

    def test_log_colors_mapping(self):
        """Test LOG_COLORS mapping contains expected entries."""
        expected_keys = [
            'User_Request', 'Analysis', 'Task', 'Classification',
            'IPythonRun', 'CmdRun', 'BrowseURL', 'Execution Result',
            'Message', 'Finish', 'TaskFinish', 'ERROR', 'Summarize'
        ]
        
        for key in expected_keys:
            assert key in LOG_COLORS
            assert isinstance(LOG_COLORS[key], str)

    @patch('infant.util.logger.DEBUG', True)
    def test_rolling_logger_start(self):
        """Test RollingLogger start method."""
        logger = RollingLogger(max_lines=3)
        
        with patch.object(logger, '_write') as mock_write:
            with patch.object(logger, '_flush') as mock_flush:
                logger.start('Starting...')
                
                mock_write.assert_called_with('\n\n\n')
                mock_flush.assert_called()

    def test_rolling_logger_move_back(self):
        """Test RollingLogger move_back method."""
        logger = RollingLogger(max_lines=3)
        
        with patch.object(logger, '_write') as mock_write:
            with patch.object(logger, '_flush') as mock_flush:
                logger.move_back()
                
                mock_write.assert_called_with('\033[F\033[F\033[F')
                mock_flush.assert_called()

    def test_rolling_logger_replace_current_line(self):
        """Test RollingLogger replace_current_line method."""
        logger = RollingLogger()
        
        with patch.object(logger, '_write') as mock_write:
            with patch.object(logger, '_flush') as mock_flush:
                logger.replace_current_line('test line')
                
                mock_write.assert_called_with('\033[2Ktest line\n')
                mock_flush.assert_called()

    def test_colored_formatter_debug_mode(self):
        """Test ColoredFormatter in debug mode."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Debug message',
            args=(),
            exc_info=None
        )
        record.msg_type = 'ERROR'
        
        with patch('infant.util.logger.DEBUG', True):
            with patch('infant.util.logger.DISABLE_COLOR_PRINTING', False):
                formatted = formatter.format(record)
                assert 'test.py:10' in formatted
                assert 'Debug message' in formatted

    def test_llm_file_handler_clear_directory(self, temp_dir):
        """Test LlmFileHandler clears directory when not in debug mode."""
        log_dir = os.path.join(temp_dir, 'llm', 'default')
        os.makedirs(log_dir, exist_ok=True)
        
        # Create a dummy file
        dummy_file = os.path.join(log_dir, 'dummy.log')
        with open(dummy_file, 'w') as f:
            f.write('dummy content')
        
        with patch('infant.util.logger.LOG_DIR', temp_dir):
            with patch('infant.util.logger.DEBUG', False):
                handler = LlmFileHandler('test_prompt')
                
                # Dummy file should be deleted
                assert not os.path.exists(dummy_file)
