"""Configuration settings for the changelog generator."""

from dataclasses import dataclass, field
from typing import Optional
import os
import re
import streamlit as st
from .exceptions import ConfigurationError, ValidationError


@dataclass
class GitHubConfig:
    """GitHub API configuration."""
    api_base_url: str = "https://api.github.com"
    per_page: int = 100
    rate_limit_delay: float = 1.0
    timeout: int = 30
    max_retries: int = 3


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 60


@dataclass
class AppConfig:
    """Main application configuration."""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    
    @property
    def github_token(self) -> Optional[str]:
        """Get GitHub token from secrets or environment."""
        try:
            return st.secrets["github"]["api_key"]
        except (KeyError, AttributeError):
            return os.getenv('GITHUB_API_KEY')
    
    @property
    def openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from secrets or environment."""
        try:
            return st.secrets["openai"]["api_key"]
        except (KeyError, AttributeError):
            return os.getenv('OPENAI_API_KEY')


def validate_github_token(token: str) -> bool:
    """Validate GitHub token format and basic structure."""
    if not token:
        return False
    
    # GitHub tokens follow specific patterns
    patterns = [
        r'^ghp_[a-zA-Z0-9]{36}$',  # Personal Access Token
        r'^gho_[a-zA-Z0-9]{36}$',  # OAuth token
        r'^ghu_[a-zA-Z0-9]{36}$',  # User token
        r'^ghs_[a-zA-Z0-9]{36}$',  # Server token
        r'^github_pat_[a-zA-Z0-9_]{22,255}$',  # Fine-grained personal access token
    ]
    
    return any(re.match(pattern, token) for pattern in patterns)


def get_secure_github_token() -> Optional[str]:
    """Securely handle GitHub token input with validation."""
    config = AppConfig()
    
    # Try to get from configuration first
    token = config.github_token
    if token and validate_github_token(token):
        return token
    
    # Fallback to UI input
    token = st.text_input(
        "Enter your GitHub token:",
        type="password",
        help="Generate at https://github.com/settings/tokens with 'repo' permissions",
        key="github_token_input"
    )
    
    if token:
        if not validate_github_token(token):
            st.error("Invalid GitHub token format. Please check your token.")
            return None
        return token
    
    return None


def get_secure_openai_key() -> Optional[str]:
    """Securely handle OpenAI API key input."""
    config = AppConfig()
    
    # Try to get from configuration first
    api_key = config.openai_api_key
    if api_key:
        return api_key
    
    st.error("OpenAI API key not configured. Please add to secrets.toml or environment variables.")
    return None


def validate_configuration() -> None:
    """Validate all required configuration is present."""
    errors = []
    
    # Check GitHub token
    github_token = get_secure_github_token()
    if not github_token:
        errors.append("Valid GitHub API token required")
    
    # Check OpenAI key
    openai_key = get_secure_openai_key()
    if not openai_key:
        errors.append("OpenAI API key required")
    
    if errors:
        raise ConfigurationError(f"Configuration errors: {'; '.join(errors)}")