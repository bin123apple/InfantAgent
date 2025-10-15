"""Unit tests for tools utility functions."""

import os
import tempfile
from unittest.mock import MagicMock, patch, mock_open

import pytest

from infant.tools.util import (
    _is_valid_filename,
    _is_valid_path,
    _create_paths,
    _check_current_file,
    _clamp,
    match_str,
    _lint_file,
    _cur_file_header,
    search_function_line_number,
    _print_window,
    is_text_file,
    update_pwd_decorator,
    CURRENT_FILE,
    CURRENT_LINE,
    WINDOW,
    MSG_FILE_UPDATED,
)


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_is_valid_filename_invalid_cases_posix(self, monkeypatch):
        monkeypatch.setattr(os, 'name', 'posix', raising=False)
        assert _is_valid_filename('') is False
        assert _is_valid_filename(None) is False
        assert _is_valid_filename('   ') is False
        assert _is_valid_filename(123) is False
        assert _is_valid_filename('a/b.txt') is False
        assert _is_valid_filename('a\0b') is False

    def test_is_valid_filename_invalid_cases_windows(self, monkeypatch):
        monkeypatch.setattr(os, 'name', 'nt', raising=False)
        for ch in '<>:"/\\|?*':
            assert _is_valid_filename(f'test{ch}.txt') is False

    def test_is_valid_path_valid_cases(self, temp_file):
        """Test _is_valid_path with valid paths."""
        assert _is_valid_path(temp_file) is True
        assert _is_valid_path(os.path.dirname(temp_file)) is True

    def test_is_valid_path_invalid_cases(self):
        """Test _is_valid_path with invalid paths."""
        assert _is_valid_path('') is False
        assert _is_valid_path(None) is False
        assert _is_valid_path(123) is False
        assert _is_valid_path('/nonexistent/path') is False

    @patch('os.path.exists')
    def test_is_valid_path_permission_error(self, mock_exists):
        """Test _is_valid_path handles PermissionError."""
        mock_exists.side_effect = PermissionError()
        assert _is_valid_path('/some/path') is False

    def test_create_paths_success(self, temp_dir):
        """Test _create_paths successfully creates directories."""
        test_path = os.path.join(temp_dir, 'new_dir', 'file.txt')
        assert _create_paths(test_path) is True
        assert os.path.exists(os.path.dirname(test_path))

    def test_create_paths_no_dirname(self):
        """Test _create_paths with filename only."""
        assert _create_paths('file.txt') is True

    @patch('os.makedirs')
    def test_create_paths_permission_error(self, mock_makedirs):
        """Test _create_paths handles PermissionError."""
        mock_makedirs.side_effect = PermissionError()
        assert _create_paths('/some/path/file.txt') is False

    def test_check_current_file_with_valid_file(self, temp_file):
        """Test _check_current_file with valid file."""
        assert _check_current_file(temp_file) is True

    def test_check_current_file_with_invalid_file(self):
        """Test _check_current_file with invalid file."""
        with pytest.raises(ValueError, match='No file open'):
            _check_current_file('/nonexistent/file.txt')

    @patch('infant.tools.util.CURRENT_FILE', '/nonexistent/file.txt')
    def test_check_current_file_with_global_invalid_file(self):
        """Test _check_current_file with invalid global CURRENT_FILE."""
        with pytest.raises(ValueError, match='No file open'):
            _check_current_file()

    def test_clamp_function(self):
        """Test _clamp function."""
        assert _clamp(5, 1, 10) == 5
        assert _clamp(0, 1, 10) == 1
        assert _clamp(15, 1, 10) == 10
        assert _clamp(-5, -10, -1) == -5
        assert _clamp(-15, -10, -1) == -10

    def test_match_str_exact_match(self):
        """Test match_str with exact match."""
        my_list = ['line 1\n', 'line 2\n', 'line 3\n']
        result = match_str('line 2', my_list, 2)
        assert result == 1

    def test_match_str_partial_match(self):
        """Test match_str with partial match."""
        my_list = ['hello world\n', 'foo bar\n', 'test line\n']
        result = match_str('world', my_list, 1)
        assert result == 0

    def test_match_str_no_match(self):
        """Test match_str with no match."""
        my_list = ['line 1\n', 'line 2\n', 'line 3\n']
        result = match_str('nonexistent', my_list, 1)
        assert result is None

    def test_match_str_empty_string(self):
        """Test match_str with empty string."""
        my_list = ['line 1\n', 'line 2\n', 'line 3\n']
        result = match_str('', my_list, 1)
        assert result is None

    def test_match_str_closest_distance(self):
        """Test match_str selects closest match by distance."""
        my_list = ['target\n', 'other\n', 'target\n']
        # Should select first target (index 0) when line_number is 1
        result = match_str('target', my_list, 1)
        assert result == 0
        
        # Should select second target (index 2) when line_number is 3
        result = match_str('target', my_list, 3)
        assert result == 2

    @patch('subprocess.run')
    def test_lint_file_python_no_errors(self, mock_run):
        """Test _lint_file with Python file and no errors."""
        mock_run.return_value.returncode = 0
        
        result = _lint_file('test.py')
        assert result == (None, None)
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'flake8' in args
        assert 'test.py' in args

    @patch('subprocess.run')
    def test_lint_file_python_with_errors(self, mock_run):
        """Test _lint_file with Python file and errors."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout.decode.return_value = 'test.py:5:10: F821 undefined name\ntest.py:10:5: E112 expected indented block'
        
        lint_error, first_error_line = _lint_file('test.py')
        
        assert lint_error.startswith('ERRORS:\n')
        assert 'F821 undefined name' in lint_error
        assert first_error_line == 5

    @patch('subprocess.run')
    def test_lint_file_python_invalid_line_number(self, mock_run):
        """Test _lint_file with invalid line number format."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout.decode.return_value = 'test.py:invalid:10: F821 error'
        
        lint_error, first_error_line = _lint_file('test.py')
        
        assert lint_error is not None
        assert first_error_line is None

    def test_lint_file_non_python(self):
        """Test _lint_file with non-Python file."""
        result = _lint_file('test.txt')
        assert result == (None, None)

    def test_cur_file_header_with_file(self):
        """Test _cur_file_header with file."""
        result = _cur_file_header('/path/to/file.txt', 100)
        expected = f'[File: {os.path.abspath("/path/to/file.txt")} (100 lines total)]\n'
        assert result == expected

    def test_cur_file_header_no_file(self):
        """Test _cur_file_header with no file."""
        result = _cur_file_header(None, 100)
        assert result == ''

    def test_search_function_line_number_found(self, sample_python_file):
        """Test search_function_line_number with existing function."""
        start_line, end_line = search_function_line_number(sample_python_file, 'hello_world')
        
        assert start_line == 1
        assert end_line == 5 # skip the blank line after function

    def test_search_function_line_number_not_found(self, sample_python_file, capsys):
        """Test search_function_line_number with non-existing function."""
        start_line, end_line = search_function_line_number(sample_python_file, 'nonexistent_function')
        
        assert start_line is None
        assert end_line is None
        
        captured = capsys.readouterr()
        assert "Function 'nonexistent_function' not found" in captured.out

    def test_search_function_line_number_file_not_found(self):
        """Test search_function_line_number with non-existing file."""
        with pytest.raises(Exception, match="File '/nonexistent/file.py' not found"):
            search_function_line_number('/nonexistent/file.py', 'some_function')

    def test_print_window_basic(self, sample_text_file):
        """Test _print_window basic functionality."""
        result = _print_window(sample_text_file, 5, 4, return_str=True)
        
        assert '3|Line 3' in result
        assert '4|Line 4' in result
        assert '5|Line 5' in result
        assert '6|Line 6' in result
        assert '7|Line 7' in result

    def test_print_window_at_beginning(self, sample_text_file):
        """Test _print_window at beginning of file."""
        result = _print_window(sample_text_file, 1, 4, return_str=True)
        
        assert '1|Line 1' in result
        assert '2|Line 2' in result
        assert 'more lines above' not in result

    def test_print_window_at_end(self, sample_text_file):
        """Test _print_window at end of file."""
        result = _print_window(sample_text_file, 10, 4, return_str=True)
        
        assert '10|Line 10' in result
        assert 'more lines below' not in result

    def test_print_window_large_window(self, sample_text_file):
        """Test _print_window with window larger than file."""
        result = _print_window(sample_text_file, 5, 20, return_str=True)
        
        # Should show entire file
        assert '1|Line 1' in result
        assert '10|Line 10' in result

    @patch('chardet.detect')
    @patch('mimetypes.guess_type')
    def test_is_text_file_mime_type(self, mock_guess_type, mock_detect):
        """Test is_text_file with MIME type detection."""
        mock_guess_type.return_value = ('text/plain', None)
        
        with patch('builtins.open', mock_open(read_data=b'test content')):
            result = is_text_file('test.txt')
        
        assert result is True

    @patch('chardet.detect')
    @patch('mimetypes.guess_type')
    def test_is_text_file_binary_content(self, mock_guess_type, mock_detect):
        """Test is_text_file with binary content."""
        mock_guess_type.return_value = (None, None)
        
        with patch('builtins.open', mock_open(read_data=b'test\x00binary')):
            result = is_text_file('test.bin')
        
        assert result is False

    @patch('chardet.detect')
    @patch('mimetypes.guess_type')
    def test_is_text_file_encoding_detection(self, mock_guess_type, mock_detect):
        """Test is_text_file with encoding detection."""
        mock_guess_type.return_value = (None, None)
        mock_detect.return_value = {'encoding': 'utf-8'}
        
        with patch('builtins.open', mock_open(read_data=b'test content')):
            result = is_text_file('test.txt')
        
        assert result is True

    @patch('chardet.detect')
    @patch('mimetypes.guess_type')
    def test_is_text_file_no_encoding(self, mock_guess_type, mock_detect):
        """Test is_text_file with no encoding detected."""
        mock_guess_type.return_value = (None, None)
        mock_detect.return_value = {'encoding': None}
        
        with patch('builtins.open', mock_open(read_data=b'test content')):
            result = is_text_file('test.txt')
        
        assert result is False

    @patch('chardet.detect')
    @patch('mimetypes.guess_type')
    def test_is_text_file_exception(self, mock_guess_type, mock_detect, capsys):
        """Test is_text_file handles exceptions."""
        mock_guess_type.side_effect = Exception('Test error')
        
        result = is_text_file('test.txt')
        
        assert result is False
        captured = capsys.readouterr()
        assert 'Error detecting file type' in captured.out

    def test_update_pwd_decorator_with_jupyter_pwd(self):
        """Test update_pwd_decorator with JUPYTER_PWD set."""
        original_cwd = os.getcwd()
        
        @update_pwd_decorator
        def test_function():
            return os.getcwd()
        
        with patch.dict(os.environ, {'JUPYTER_PWD': '/tmp'}):
            with patch('os.chdir') as mock_chdir:
                result = test_function()
                
                # Should change to JUPYTER_PWD and back
                mock_chdir.assert_any_call('/tmp')
                mock_chdir.assert_any_call(original_cwd)

    def test_update_pwd_decorator_exception_handling(self):
        """Test update_pwd_decorator restores directory on exception."""
        original_cwd = os.getcwd()
        
        @update_pwd_decorator
        def test_function():
            raise ValueError('Test error')
        
        with patch.dict(os.environ, {'JUPYTER_PWD': '/tmp'}):
            with patch('os.chdir') as mock_chdir:
                with pytest.raises(ValueError, match='Test error'):
                    test_function()
                
                # Should still restore original directory
                mock_chdir.assert_any_call('/tmp')
                mock_chdir.assert_any_call(original_cwd)

    def test_constants(self):
        """Test module constants."""
        assert isinstance(WINDOW, int)
        assert WINDOW > 0
        assert isinstance(MSG_FILE_UPDATED, str)
        assert 'File updated' in MSG_FILE_UPDATED