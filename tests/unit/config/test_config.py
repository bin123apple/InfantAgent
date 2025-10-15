"""Unit tests for the Config class."""

import os
import sys
import tempfile
import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

from infant.config import Config, LitellmParams, VllmParams


class TestConfig:
    """Test cases for the Config class."""

    def test_config_init_with_defaults(self):
        """Test Config initialization with default values."""
        config = Config()
        
        # Test default values
        assert config.model == 'claude-sonnet-4-20250514'
        assert config.max_iterations == 100
        assert config.max_voting == 5
        assert config.temperature == 1.0
        assert config.top_p == 0.5
        assert config.num_retries == 5
        assert config.retry_min_wait == 5
        assert config.retry_max_wait == 60
        assert config.max_chars == 5_000_000
        assert config.run_as_infant is True
        assert config.debug is False
        assert config.enable_auto_lint is True

    def test_config_init_with_env_vars(self, monkeypatch, tmp_path):
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-api-key')

        fake_toml = tmp_path / "config.toml"
        fake_toml.write_text("") 
        mod_name = "infant.config"
        sys.modules.pop(mod_name, None)
        m = importlib.import_module(mod_name)

        monkeypatch.setattr(m, "CONFIG_FILE", fake_toml, raising=False)
        monkeypatch.setattr(m.toml, "load", lambda _: {}, raising=True)

        m = importlib.reload(m)

        Config = m.Config
        cfg = Config()
        assert cfg.api_key == 'test-api-key'

    def test_config_workspace_paths(self):
        """Test workspace path configuration."""
        config = Config()
        
        # Test default workspace paths
        expected_workspace_base = os.path.join(os.getcwd(), 'workspace')
        assert config.workspace_base == expected_workspace_base
        assert config.workspace_mount_path == expected_workspace_base
        assert config.workspace_mount_path_in_computer == '/workspace'

    def test_config_computer_attributes(self):
        """Test computer-related configuration attributes."""
        config = Config()
        
        assert config.runtime == 'server'
        assert config.file_store == 'memory'
        assert config.computer_type == 'ssh'
        assert config.ssh_hostname == 'localhost'
        assert config.computer_timeout == 120
        assert config.use_host_network is False

    def test_config_vllm_attributes(self):
        """Test VLLM-related configuration attributes."""
        config = Config()
        
        assert config.model_oss == 'ByteDance-Seed/UI-TARS-1.5-7B'
        assert config.tensor_parallel_size == 1
        assert config.max_model_len == 8192
        assert config.vllm_temperature == 0
        assert config.vllm_top_p == 1.0
        assert config.max_tokens == 1024

    def test_config_agent_attributes(self):
        """Test agent-related configuration attributes."""
        config = Config()
        
        assert config.max_planning_iterations == 5
        assert config.max_execution_iterations == 10
        assert config.max_self_modify_basic == 20
        assert config.max_self_modify_advanced == 7
        assert config.max_action_times == 30
        assert config.max_finish_retry == 3
        assert config.max_message_retry == 3
        assert config.max_continuous_errors == 10
        assert config.use_oss_llm is True

    def test_finalize_config_workspace_paths(self):
        """Test finalize_config method for workspace path handling."""
        config = Config()
        config.workspace_base = './test_workspace'
        config.workspace_mount_path = 'undefined'
        
        config.finalize_config()
        
        # Should convert to absolute path
        assert os.path.isabs(config.workspace_base)
        assert os.path.isabs(config.workspace_mount_path)
        assert config.workspace_mount_path == os.path.abspath('./test_workspace')

    def test_finalize_config_local_computer_type(self):
        """Test finalize_config with local computer type."""
        config = Config()
        config.computer_type = 'local'
        config.workspace_mount_path = '/some/path'
        
        config.finalize_config()
        
        # For local computer type, workspace paths should be the same
        assert config.workspace_mount_path_in_computer == config.workspace_mount_path

    def test_finalize_config_workspace_mount_rewrite(self):
        """Test finalize_config with workspace mount rewrite."""
        config = Config()
        config.workspace_base = '/original/path/workspace'
        config.workspace_mount_rewrite = '/original:/rewritten'
        
        config.finalize_config()
        
        assert config.workspace_mount_path == '/rewritten/path/workspace'

    def test_finalize_config_embedding_base_url(self):
        """Test finalize_config sets embedding_base_url from base_url."""
        config = Config()
        config.base_url = 'https://api.example.com'
        config.embedding_base_url = None
        
        config.finalize_config()
        
        assert config.embedding_base_url == 'https://api.example.com'

    def test_finalize_config_cache_dir_creation(self, temp_dir):
        """Test finalize_config creates cache directory."""
        config = Config()
        cache_path = os.path.join(temp_dir, 'test_cache')
        config.cache_dir = cache_path
        
        config.finalize_config()
        
        assert os.path.exists(cache_path)
        assert os.path.isdir(cache_path)

    def test_get_litellm_params(self):
        """Test get_litellm_params method."""
        config = Config()
        config.model = 'test-model'
        config.api_key = 'test-key'
        config.temperature = 0.8
        
        params = config.get_litellm_params()
        
        assert params.model == 'test-model'
        assert params.api_key == 'test-key'
        assert params.temperature == 0.8
        assert params.num_retries == 5

    def test_get_litellm_params_with_overrides(self):
        """Test get_litellm_params method with overrides."""
        config = Config()
        
        overrides = {
            'model': 'override-model',
            'temperature': 0.5
        }
        params = config.get_litellm_params(overrides)
        
        assert params.model == 'override-model'
        assert params.temperature == 0.5

    def test_get_vllm_params(self):
        """Test get_vllm_params method."""
        config = Config()
        config.model_oss = 'test-oss-model'
        config.tensor_parallel_size = 2
        
        params = config.get_vllm_params()
        
        assert params.model_oss == 'test-oss-model'
        assert params.tensor_parallel_size == 2

    def test_config_str_representation(self):
        """Test string representation of Config."""
        config = Config()
        config_str = str(config)
        
        # Check that all sections are present
        assert '### litellm Attributes ###' in config_str
        assert '### vllm Attributes ###' in config_str
        assert '### Agent Attributes ###' in config_str
        assert '### Computer Attributes ###' in config_str
        
        # Check that some key values are present
        assert 'model:' in config_str
        assert 'max_iterations:' in config_str

    def test_config_with_custom_values(self):
        """Test Config with custom values."""
        config = Config(
            model='custom-model',
            temperature=0.7,
            max_iterations=50,
            debug=True
        )
        
        assert config.model == 'custom-model'
        assert config.temperature == 0.7
        assert config.max_iterations == 50
        assert config.debug is True

    def test_config_computer_user_id_fallback(self):
        """Test computer_user_id fallback when getuid is not available."""
        config = Config()
        
        # Should either be the actual user ID or fallback to 1000
        assert isinstance(config.computer_user_id, int)
        assert config.computer_user_id >= 0

    def test_config_boolean_attributes(self):
        """Test boolean configuration attributes."""
        config = Config()
        
        # Test various boolean flags
        assert isinstance(config.run_as_infant, bool)
        assert isinstance(config.debug, bool)
        assert isinstance(config.enable_auto_lint, bool)
        assert isinstance(config.use_host_network, bool)
        assert isinstance(config.disable_color, bool)
        assert isinstance(config.initialize_plugins, bool)
        assert isinstance(config.consistant_computer, bool)
        assert isinstance(config.text_only_docker, bool)

    def test_config_numeric_constraints(self):
        """Test numeric configuration constraints."""
        config = Config()
        
        # Test that numeric values are within reasonable ranges
        assert config.max_iterations > 0
        assert config.max_voting > 0
        assert config.num_retries >= 0
        assert config.retry_min_wait >= 0
        assert config.retry_max_wait >= config.retry_min_wait
        assert config.temperature >= 0
        assert config.top_p >= 0 and config.top_p <= 1
        assert config.computer_timeout > 0