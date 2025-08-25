"""Unit tests for config.settings module."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

from config.settings import (
    GitHubConfig,
    OpenAIConfig,
    AppConfig,
    validate_github_token,
    get_secure_github_token,
    get_secure_openai_key,
    validate_configuration
)
from config.exceptions import ConfigurationError


@pytest.mark.unit
class TestGitHubConfig:
    """Test GitHubConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = GitHubConfig()
        
        assert config.api_base_url == "https://api.github.com"
        assert config.per_page == 100
        assert config.rate_limit_delay == 1.0
        assert config.timeout == 30
        assert config.max_retries == 3

    def test_custom_values(self):
        """Test setting custom configuration values."""
        config = GitHubConfig(
            api_base_url="https://github.enterprise.com/api/v3",
            per_page=50,
            rate_limit_delay=2.0,
            timeout=60,
            max_retries=5
        )
        
        assert config.api_base_url == "https://github.enterprise.com/api/v3"
        assert config.per_page == 50
        assert config.rate_limit_delay == 2.0
        assert config.timeout == 60
        assert config.max_retries == 5

    def test_dataclass_properties(self):
        """Test that GitHubConfig is a proper dataclass."""
        config = GitHubConfig()
        config_dict = asdict(config)
        
        expected_keys = {
            'api_base_url', 'per_page', 'rate_limit_delay', 
            'timeout', 'max_retries'
        }
        assert set(config_dict.keys()) == expected_keys


@pytest.mark.unit
class TestOpenAIConfig:
    """Test OpenAIConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = OpenAIConfig()
        
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens is None
        assert config.timeout == 60

    def test_custom_values(self):
        """Test setting custom configuration values."""
        config = OpenAIConfig(
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=2048,
            timeout=120
        )
        
        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.timeout == 120

    def test_dataclass_properties(self):
        """Test that OpenAIConfig is a proper dataclass."""
        config = OpenAIConfig()
        config_dict = asdict(config)
        
        expected_keys = {'model', 'temperature', 'max_tokens', 'timeout'}
        assert set(config_dict.keys()) == expected_keys


@pytest.mark.unit
class TestAppConfig:
    """Test AppConfig dataclass."""

    def test_default_initialization(self):
        """Test default initialization of AppConfig."""
        config = AppConfig()
        
        assert isinstance(config.github, GitHubConfig)
        assert isinstance(config.openai, OpenAIConfig)
        assert config.github.api_base_url == "https://api.github.com"
        assert config.openai.model == "gpt-4o"

    def test_custom_initialization(self):
        """Test custom initialization of AppConfig."""
        github_config = GitHubConfig(per_page=50)
        openai_config = OpenAIConfig(model="gpt-3.5-turbo")
        
        config = AppConfig(github=github_config, openai=openai_config)
        
        assert config.github.per_page == 50
        assert config.openai.model == "gpt-3.5-turbo"

    def test_github_token_from_secrets(self):
        """Test getting GitHub token from Streamlit secrets."""
        mock_token = "ghp_1234567890123456789012345678901234567890"
        
        with patch('streamlit.secrets') as mock_secrets:
            mock_secrets.__getitem__.return_value = {"api_key": mock_token}
            
            config = AppConfig()
            result = config.github_token
            
            assert result == mock_token

    def test_github_token_from_environment(self):
        """Test getting GitHub token from environment variable."""
        mock_token = "ghp_1234567890123456789012345678901234567890"
        
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict(os.environ, {'GITHUB_API_KEY': mock_token}):
            
            mock_secrets.__getitem__.side_effect = KeyError("No secrets")
            
            config = AppConfig()
            result = config.github_token
            
            assert result == mock_token

    def test_github_token_not_found(self):
        """Test when GitHub token is not found."""
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict(os.environ, {}, clear=True):
            
            mock_secrets.__getitem__.side_effect = KeyError("No secrets")
            
            config = AppConfig()
            result = config.github_token
            
            assert result is None

    def test_openai_api_key_from_secrets(self):
        """Test getting OpenAI API key from Streamlit secrets."""
        mock_key = "sk-1234567890123456789012345678901234567890123456789012345678"
        
        with patch('streamlit.secrets') as mock_secrets:
            mock_secrets.__getitem__.return_value = {"api_key": mock_key}
            
            config = AppConfig()
            result = config.openai_api_key
            
            assert result == mock_key

    def test_openai_api_key_from_environment(self):
        """Test getting OpenAI API key from environment variable."""
        mock_key = "sk-1234567890123456789012345678901234567890123456789012345678"
        
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict(os.environ, {'OPENAI_API_KEY': mock_key}):
            
            mock_secrets.__getitem__.side_effect = KeyError("No secrets")
            
            config = AppConfig()
            result = config.openai_api_key
            
            assert result == mock_key

    def test_openai_api_key_not_found(self):
        """Test when OpenAI API key is not found."""
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict(os.environ, {}, clear=True):
            
            mock_secrets.__getitem__.side_effect = KeyError("No secrets")
            
            config = AppConfig()
            result = config.openai_api_key
            
            assert result is None


@pytest.mark.unit
class TestValidateGitHubToken:
    """Test validate_github_token function."""

    def test_valid_personal_access_token(self):
        """Test validation of valid personal access tokens."""
        valid_tokens = [
            "ghp_" + "a" * 36,
            "ghp_1234567890123456789012345678901234567890",
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890AB"
        ]
        
        for token in valid_tokens:
            assert validate_github_token(token) is True

    def test_valid_oauth_token(self):
        """Test validation of valid OAuth tokens."""
        valid_tokens = [
            "gho_" + "a" * 36,
            "gho_1234567890123456789012345678901234567890"
        ]
        
        for token in valid_tokens:
            assert validate_github_token(token) is True

    def test_valid_user_token(self):
        """Test validation of valid user tokens."""
        valid_tokens = [
            "ghu_" + "a" * 36,
            "ghu_1234567890123456789012345678901234567890"
        ]
        
        for token in valid_tokens:
            assert validate_github_token(token) is True

    def test_valid_server_token(self):
        """Test validation of valid server tokens."""
        valid_tokens = [
            "ghs_" + "a" * 36,
            "ghs_1234567890123456789012345678901234567890"
        ]
        
        for token in valid_tokens:
            assert validate_github_token(token) is True

    def test_valid_fine_grained_token(self):
        """Test validation of valid fine-grained personal access tokens."""
        valid_tokens = [
            "github_pat_" + "a" * 22,
            "github_pat_" + "A" * 255,  # Maximum length
            "github_pat_1234567890_abcdefghij",
            "github_pat_AbCdEfGhIjKlMnOpQrSt_123"
        ]
        
        for token in valid_tokens:
            assert validate_github_token(token) is True

    def test_invalid_token_formats(self):
        """Test rejection of invalid token formats."""
        invalid_tokens = [
            "",  # Empty string
            "invalid_token",  # Wrong format
            "ghp_short",  # Too short
            "ghp_" + "a" * 35,  # Too short
            "ghp_" + "a" * 37,  # Too long
            "xyz_" + "a" * 36,  # Invalid prefix
            "github_pat_short",  # Too short for fine-grained
            "github_pat_" + "a" * 21,  # Too short for fine-grained
            "github_pat_" + "a" * 256,  # Too long for fine-grained
            None  # None value
        ]
        
        for token in invalid_tokens:
            assert validate_github_token(token) is False

    def test_edge_cases(self):
        """Test edge cases in token validation."""
        edge_cases = [
            ("ghp_" + "0" * 36, True),  # All zeros
            ("ghp_" + "Z" * 36, True),  # All uppercase
            ("github_pat_" + "_" * 22, True),  # Underscores only
            ("ghp_" + "a" * 35 + ".", False),  # Invalid character
            ("ghp " + "a" * 36, False),  # Space instead of underscore
        ]
        
        for token, expected in edge_cases:
            assert validate_github_token(token) == expected


@pytest.mark.unit
class TestGetSecureGitHubToken:
    """Test get_secure_github_token function."""

    def test_get_token_from_config(self, mock_github_token):
        """Test getting token from configuration."""
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('config.settings.validate_github_token', return_value=True):
            
            mock_config_instance = Mock()
            mock_config_instance.github_token = mock_github_token
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_github_token()
            
            assert result == mock_github_token

    def test_get_token_from_ui_input(self, mock_github_token):
        """Test getting token from UI input."""
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('config.settings.validate_github_token', return_value=True), \
             patch('streamlit.text_input', return_value=mock_github_token) as mock_input:
            
            mock_config_instance = Mock()
            mock_config_instance.github_token = None
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_github_token()
            
            assert result == mock_github_token
            mock_input.assert_called_once()

    def test_invalid_token_from_config(self):
        """Test handling of invalid token from configuration."""
        invalid_token = "invalid_token"
        
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('config.settings.validate_github_token', return_value=False), \
             patch('streamlit.text_input', return_value="") as mock_input:
            
            mock_config_instance = Mock()
            mock_config_instance.github_token = invalid_token
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_github_token()
            
            assert result is None
            mock_input.assert_called_once()

    def test_invalid_token_from_ui(self):
        """Test handling of invalid token from UI input."""
        invalid_token = "invalid_token"
        
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('config.settings.validate_github_token', return_value=False), \
             patch('streamlit.text_input', return_value=invalid_token), \
             patch('streamlit.error') as mock_error:
            
            mock_config_instance = Mock()
            mock_config_instance.github_token = None
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_github_token()
            
            assert result is None
            mock_error.assert_called_with("Invalid GitHub token format. Please check your token.")

    def test_no_token_provided(self):
        """Test when no token is provided."""
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('streamlit.text_input', return_value=""):
            
            mock_config_instance = Mock()
            mock_config_instance.github_token = None
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_github_token()
            
            assert result is None

    def test_ui_input_parameters(self):
        """Test that UI input is configured correctly."""
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('streamlit.text_input') as mock_input:
            
            mock_config_instance = Mock()
            mock_config_instance.github_token = None
            mock_app_config.return_value = mock_config_instance
            mock_input.return_value = ""
            
            get_secure_github_token()
            
            # Check that text_input is called with correct parameters
            call_args = mock_input.call_args
            assert call_args[0][0] == "Enter your GitHub token:"
            assert call_args[1]['type'] == "password"
            assert "github.com/settings/tokens" in call_args[1]['help']
            assert call_args[1]['key'] == "github_token_input"


@pytest.mark.unit
class TestGetSecureOpenAiKey:
    """Test get_secure_openai_key function."""

    def test_get_key_from_config(self, mock_openai_key):
        """Test getting OpenAI key from configuration."""
        with patch('config.settings.AppConfig') as mock_app_config:
            mock_config_instance = Mock()
            mock_config_instance.openai_api_key = mock_openai_key
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_openai_key()
            
            assert result == mock_openai_key

    def test_key_not_configured(self):
        """Test when OpenAI key is not configured."""
        with patch('config.settings.AppConfig') as mock_app_config, \
             patch('streamlit.error') as mock_error:
            
            mock_config_instance = Mock()
            mock_config_instance.openai_api_key = None
            mock_app_config.return_value = mock_config_instance
            
            result = get_secure_openai_key()
            
            assert result is None
            mock_error.assert_called_with(
                "OpenAI API key not configured. Please add to secrets.toml or environment variables."
            )


@pytest.mark.unit
class TestValidateConfiguration:
    """Test validate_configuration function."""

    def test_valid_configuration(self, mock_github_token, mock_openai_key):
        """Test validation with valid configuration."""
        with patch('config.settings.get_secure_github_token', return_value=mock_github_token), \
             patch('config.settings.get_secure_openai_key', return_value=mock_openai_key):
            
            # Should not raise any exception
            validate_configuration()

    def test_missing_github_token(self, mock_openai_key):
        """Test validation with missing GitHub token."""
        with patch('config.settings.get_secure_github_token', return_value=None), \
             patch('config.settings.get_secure_openai_key', return_value=mock_openai_key):
            
            with pytest.raises(ConfigurationError, match="Valid GitHub API token required"):
                validate_configuration()

    def test_missing_openai_key(self, mock_github_token):
        """Test validation with missing OpenAI API key."""
        with patch('config.settings.get_secure_github_token', return_value=mock_github_token), \
             patch('config.settings.get_secure_openai_key', return_value=None):
            
            with pytest.raises(ConfigurationError, match="OpenAI API key required"):
                validate_configuration()

    def test_missing_both_keys(self):
        """Test validation with both keys missing."""
        with patch('config.settings.get_secure_github_token', return_value=None), \
             patch('config.settings.get_secure_openai_key', return_value=None):
            
            with pytest.raises(ConfigurationError) as exc_info:
                validate_configuration()
            
            error_message = str(exc_info.value)
            assert "Valid GitHub API token required" in error_message
            assert "OpenAI API key required" in error_message

    def test_configuration_error_message_format(self):
        """Test that configuration error message is properly formatted."""
        with patch('config.settings.get_secure_github_token', return_value=None), \
             patch('config.settings.get_secure_openai_key', return_value=None):
            
            with pytest.raises(ConfigurationError) as exc_info:
                validate_configuration()
            
            error_message = str(exc_info.value)
            assert "Configuration errors:" in error_message
            assert ";" in error_message  # Multiple errors separated by semicolon


@pytest.mark.unit
class TestConfigurationIntegration:
    """Test integration between configuration components."""

    def test_full_config_flow(self, mock_github_token, mock_openai_key):
        """Test complete configuration flow."""
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict(os.environ, {
                 'GITHUB_API_KEY': mock_github_token,
                 'OPENAI_API_KEY': mock_openai_key
             }):
            
            # Simulate secrets not available
            mock_secrets.__getitem__.side_effect = KeyError("No secrets")
            
            # Create config and test all properties
            config = AppConfig()
            
            assert config.github_token == mock_github_token
            assert config.openai_api_key == mock_openai_key
            assert isinstance(config.github, GitHubConfig)
            assert isinstance(config.openai, OpenAIConfig)

    def test_secrets_precedence_over_env(self, mock_github_token, mock_openai_key):
        """Test that Streamlit secrets take precedence over environment variables."""
        env_github_token = "env_github_token"
        env_openai_key = "env_openai_key"
        
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict(os.environ, {
                 'GITHUB_API_KEY': env_github_token,
                 'OPENAI_API_KEY': env_openai_key
             }):
            
            # Setup secrets to return different values
            def mock_getitem(key):
                if key == "github":
                    return {"api_key": mock_github_token}
                elif key == "openai":
                    return {"api_key": mock_openai_key}
                else:
                    raise KeyError(f"No secret for {key}")
            
            mock_secrets.__getitem__.side_effect = mock_getitem
            
            config = AppConfig()
            
            # Should use secrets, not environment
            assert config.github_token == mock_github_token
            assert config.openai_api_key == mock_openai_key
            assert config.github_token != env_github_token
            assert config.openai_api_key != env_openai_key

    def test_config_modification(self):
        """Test that configuration can be modified after creation."""
        config = AppConfig()
        
        # Modify GitHub config
        config.github.per_page = 200
        config.github.timeout = 45
        
        # Modify OpenAI config
        config.openai.model = "gpt-3.5-turbo"
        config.openai.temperature = 0.5
        
        assert config.github.per_page == 200
        assert config.github.timeout == 45
        assert config.openai.model == "gpt-3.5-turbo"
        assert config.openai.temperature == 0.5

    def test_config_independence(self):
        """Test that multiple config instances are independent."""
        config1 = AppConfig()
        config2 = AppConfig()
        
        # Modify one config
        config1.github.per_page = 150
        config1.openai.temperature = 0.3
        
        # Other config should remain unchanged
        assert config2.github.per_page == 100  # Default value
        assert config2.openai.temperature == 0.7  # Default value

    def test_environment_variable_edge_cases(self):
        """Test edge cases with environment variables."""
        edge_cases = {
            '': None,  # Empty string
            ' ': ' ',  # Whitespace
            'None': 'None',  # String "None"
        }
        
        for env_value, expected in edge_cases.items():
            with patch('streamlit.secrets') as mock_secrets, \
                 patch.dict(os.environ, {'GITHUB_API_KEY': env_value}, clear=True):
                
                mock_secrets.__getitem__.side_effect = KeyError("No secrets")
                
                config = AppConfig()
                result = config.github_token
                
                if expected is None:
                    assert result is None or result == ""
                else:
                    assert result == expected