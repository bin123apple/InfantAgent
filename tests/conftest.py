"""Shared fixtures for InfantAgent tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file for testing."""
    temp_file_path = os.path.join(temp_dir, 'test_file.txt')
    with open(temp_file_path, 'w') as f:
        f.write('test content\nline 2\nline 3\n')
    yield temp_file_path


@pytest.fixture
def mock_logger():
    """Mock logger to suppress logging during tests."""
    with patch('infant.util.logger.logger') as mock_log:
        yield mock_log


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables for testing."""
    # Clear common environment variables that might affect tests
    env_vars_to_clear = [
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY', 
        'GOOGLE_API_KEY',
        'JUPYTER_PWD',
        'ENABLE_AUTO_LINT',
    ]
    
    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)
    
    yield monkeypatch


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file for testing."""
    content = '''def hello_world():
    """A simple hello world function."""
    print("Hello, World!")
    return "Hello, World!"

def add_numbers(a, b):
    """Add two numbers together."""
    return a + b

class TestClass:
    def method_one(self):
        pass
    
    def method_two(self):
        pass
'''
    file_path = os.path.join(temp_dir, 'sample.py')
    with open(file_path, 'w') as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_text_file(temp_dir):
    """Create a sample text file for testing."""
    content = '''Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
'''
    file_path = os.path.join(temp_dir, 'sample.txt')
    with open(file_path, 'w') as f:
        f.write(content)
    yield file_path


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing external commands."""
    with patch('subprocess.run') as mock_run:
        yield mock_run