"""Custom exceptions for the changelog generator."""

from typing import Optional


class ChangelogGeneratorError(Exception):
    """Base exception for changelog generator."""
    pass


class GitHubAPIError(ChangelogGeneratorError):
    """GitHub API related errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class OpenAIAPIError(ChangelogGeneratorError):
    """OpenAI API related errors."""
    pass


class ConfigurationError(ChangelogGeneratorError):
    """Configuration related errors."""
    pass


class ValidationError(ChangelogGeneratorError):
    """Input validation errors."""
    pass