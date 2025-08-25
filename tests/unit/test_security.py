"""Unit tests for utils.security module."""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from utils.security import (
    sanitize_commit_message,
    sanitize_api_response,
    validate_repository_url,
    filter_sensitive_logs,
    show_privacy_notice
)


@pytest.mark.unit
@pytest.mark.security
class TestSanitizeCommitMessage:
    """Test sanitize_commit_message function."""

    def test_remove_email_addresses(self):
        """Test removal of email addresses."""
        # Setup
        message = "Fix bug reported by john.doe@example.com and admin@company.org"
        
        # Execute
        result = sanitize_commit_message(message)
        
        # Assert
        assert "john.doe@example.com" not in result
        assert "admin@company.org" not in result
        assert "[EMAIL_REMOVED]" in result
        assert "Fix bug reported by [EMAIL_REMOVED] and [EMAIL_REMOVED]" == result

    def test_remove_ip_addresses(self):
        """Test removal of IP addresses."""
        # Setup
        message = "Connect to server at 192.168.1.100 and backup at 10.0.0.1"
        
        # Execute
        result = sanitize_commit_message(message)
        
        # Assert
        assert "192.168.1.100" not in result
        assert "10.0.0.1" not in result
        assert "[IP_REMOVED]" in result
        assert "Connect to server at [IP_REMOVED] and backup at [IP_REMOVED]" == result

    def test_remove_potential_secrets(self):
        """Test removal of potential API keys/secrets."""
        # Setup
        message = "API key: abc123def456789012345678901234567890 updated"
        
        # Execute
        result = sanitize_commit_message(message)
        
        # Assert
        assert "abc123def456789012345678901234567890" not in result
        assert "[POTENTIAL_SECRET_REMOVED]" in result
        assert "API key: [POTENTIAL_SECRET_REMOVED] updated" == result

    def test_remove_urls(self):
        """Test removal of URLs."""
        # Setup
        message = "Check https://api.example.com/users?token=secret for details"
        
        # Execute
        result = sanitize_commit_message(message)
        
        # Assert
        assert "https://api.example.com/users?token=secret" not in result
        assert "[URL_REMOVED]" in result
        assert "Check [URL_REMOVED] for details" == result

    def test_multiple_patterns_in_single_message(self):
        """Test handling of multiple sensitive patterns in one message."""
        # Setup
        message = "Contact admin@example.com at 192.168.1.1 with key abc123def456789012345678901234567890"
        
        # Execute
        result = sanitize_commit_message(message)
        
        # Assert
        assert "admin@example.com" not in result
        assert "192.168.1.1" not in result
        assert "abc123def456789012345678901234567890" not in result
        assert "[EMAIL_REMOVED]" in result
        assert "[IP_REMOVED]" in result
        assert "[POTENTIAL_SECRET_REMOVED]" in result

    def test_non_string_input(self):
        """Test handling of non-string input."""
        # Setup
        non_string_inputs = [123, None, [], {}]
        
        for input_value in non_string_inputs:
            # Execute
            result = sanitize_commit_message(input_value)
            
            # Assert
            assert result == str(input_value)

    def test_empty_string(self):
        """Test handling of empty string."""
        # Execute
        result = sanitize_commit_message("")
        
        # Assert
        assert result == ""

    def test_clean_message_unchanged(self):
        """Test that clean messages remain unchanged."""
        # Setup
        clean_message = "Fix authentication bug in login module"
        
        # Execute
        result = sanitize_commit_message(clean_message)
        
        # Assert
        assert result == clean_message

    def test_edge_case_patterns(self):
        """Test edge cases in pattern matching."""
        test_cases = [
            ("Visit http://example.com for info", "Visit [URL_REMOVED] for info"),
            ("Email me at test@test.co.uk please", "Email me at [EMAIL_REMOVED] please"),
            ("Server IP is 255.255.255.255", "Server IP is [IP_REMOVED]"),
            ("Token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0", "Token: [POTENTIAL_SECRET_REMOVED]"),
        ]
        
        for original, expected in test_cases:
            result = sanitize_commit_message(original)
            assert result == expected, f"Failed for: {original}"


@pytest.mark.unit
@pytest.mark.security
class TestSanitizeApiResponse:
    """Test sanitize_api_response function."""

    def test_sanitize_dict_with_allowed_keys(self):
        """Test sanitization of dictionary with allowed keys."""
        # Setup
        data = {
            'title': 'Test PR',
            'number': 123,
            'merged_at': '2024-01-01T00:00:00Z',
            'malicious_key': '<script>alert("xss")</script>',
            'sha': 'abc123def456'
        }
        
        # Execute
        result = sanitize_api_response(data)
        
        # Assert
        assert 'title' in result
        assert 'number' in result
        assert 'merged_at' in result
        assert 'sha' in result
        assert 'malicious_key' not in result
        assert result['title'] == 'Test PR'
        assert result['number'] == 123

    def test_sanitize_nested_dict(self):
        """Test sanitization of nested dictionaries."""
        # Setup
        data = {
            'head': {
                'repo': {
                    'description': 'Test repository',
                    'private_key': 'secret123'
                },
                'malicious': 'data'
            },
            'commit': {
                'message': 'Test commit',
                'secret_data': 'classified'
            }
        }
        
        # Execute
        result = sanitize_api_response(data)
        
        # Assert
        assert 'head' in result
        assert 'commit' in result
        assert 'repo' in result['head']
        assert 'description' in result['head']['repo']
        assert 'private_key' not in result['head']['repo']
        assert 'malicious' not in result['head']
        assert 'secret_data' not in result['commit']

    def test_sanitize_list(self):
        """Test sanitization of lists."""
        # Setup
        data = [
            {
                'title': 'PR 1',
                'number': 123,
                'malicious': '<script>alert("xss")</script>'
            },
            {
                'title': 'PR 2',
                'number': 124,
                'dangerous': 'payload'
            }
        ]
        
        # Execute
        result = sanitize_api_response(data)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert all('title' in item for item in result)
        assert all('number' in item for item in result)
        assert all('malicious' not in item for item in result)
        assert all('dangerous' not in item for item in result)

    def test_sanitize_string_dangerous_chars(self):
        """Test sanitization of strings with dangerous characters."""
        # Setup
        dangerous_strings = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '"; DROP TABLE users; --',
            "'; DELETE FROM secrets; --"
        ]
        
        for dangerous_string in dangerous_strings:
            # Execute
            result = sanitize_api_response(dangerous_string)
            
            # Assert
            assert '<' not in result
            assert '>' not in result
            assert '"' not in result
            assert "'" not in result
            assert ';' not in result
            assert '\\' not in result

    def test_sanitize_safe_string(self):
        """Test that safe strings remain unchanged."""
        # Setup
        safe_string = "This is a safe commit message with numbers 123 and symbols !@#$%^&*()"
        
        # Execute
        result = sanitize_api_response(safe_string)
        
        # Assert
        assert result == "This is a safe commit message with numbers 123 and symbols !@#$%^&*()"

    def test_sanitize_primitive_types(self):
        """Test sanitization of primitive types."""
        test_cases = [
            (123, 123),
            (123.45, 123.45),
            (True, True),
            (None, None)
        ]
        
        for input_value, expected in test_cases:
            result = sanitize_api_response(input_value)
            assert result == expected


@pytest.mark.unit
@pytest.mark.security
class TestValidateRepositoryUrl:
    """Test validate_repository_url function."""

    def test_valid_github_url(self):
        """Test validation of valid GitHub URLs."""
        valid_urls = [
            "https://github.com/owner/repo",
            "https://github.com/test-owner/test-repo",
            "https://github.com/user123/project_name",
            "https://github.com/org/repo-name"
        ]
        
        for url in valid_urls:
            # Execute
            owner, repo = validate_repository_url(url)
            
            # Assert
            assert owner is not None
            assert repo is not None
            assert isinstance(owner, str)
            assert isinstance(repo, str)

    def test_invalid_scheme(self):
        """Test rejection of non-HTTPS URLs."""
        invalid_urls = [
            "http://github.com/owner/repo",
            "ftp://github.com/owner/repo",
            "github.com/owner/repo"
        ]
        
        for url in invalid_urls:
            # Execute & Assert
            with pytest.raises(ValueError, match="Only HTTPS URLs are allowed"):
                validate_repository_url(url)

    def test_invalid_domain(self):
        """Test rejection of non-GitHub domains."""
        invalid_urls = [
            "https://gitlab.com/owner/repo",
            "https://bitbucket.org/owner/repo",
            "https://evil.com/owner/repo",
            "https://github.evil.com/owner/repo"
        ]
        
        for url in invalid_urls:
            # Execute & Assert
            with pytest.raises(ValueError, match="Only github.com URLs are allowed"):
                validate_repository_url(url)

    def test_invalid_path_format(self):
        """Test rejection of invalid path formats."""
        invalid_urls = [
            "https://github.com/owner",  # Missing repo
            "https://github.com/",  # Empty path
            "https://github.com/owner/repo/extra",  # Extra path
            "https://github.com/owner/",  # Trailing slash only
            "https://github.com//repo"  # Empty owner
        ]
        
        for url in invalid_urls:
            # Execute & Assert
            with pytest.raises(ValueError, match="Invalid repository URL format"):
                validate_repository_url(url)

    def test_blocked_owner_patterns(self):
        """Test rejection of blocked owner patterns."""
        blocked_urls = [
            "https://github.com/admin/repo",
            "https://github.com/api/repo",
            "https://github.com/www/repo",
            "https://github.com/root/repo",
            "https://github.com/system/repo"
        ]
        
        for url in blocked_urls:
            # Execute & Assert
            with pytest.raises(ValueError, match="Repository owner contains blocked pattern"):
                validate_repository_url(url)

    def test_url_length_validation(self):
        """Test URL length validation."""
        # Test empty/None URL
        with pytest.raises(ValueError, match="Invalid URL length"):
            validate_repository_url("")
        
        with pytest.raises(ValueError, match="Invalid URL length"):
            validate_repository_url(None)
        
        # Test overly long URL
        long_url = "https://github.com/" + "a" * 200 + "/repo"
        with pytest.raises(ValueError, match="Invalid URL length"):
            validate_repository_url(long_url)

    def test_special_characters_in_names(self):
        """Test handling of special characters in owner/repo names."""
        # Valid special characters
        valid_urls = [
            "https://github.com/test-user/test-repo",
            "https://github.com/user_123/repo.name",
            "https://github.com/org-name/project_name"
        ]
        
        for url in valid_urls:
            owner, repo = validate_repository_url(url)
            assert owner is not None
            assert repo is not None

        # Invalid special characters
        invalid_urls = [
            "https://github.com/test@user/repo",
            "https://github.com/user/repo#hash",
            "https://github.com/user/repo?param=value"
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                validate_repository_url(url)

    def test_case_insensitive_blocking(self):
        """Test that blocked patterns work case-insensitively."""
        blocked_urls = [
            "https://github.com/ADMIN/repo",
            "https://github.com/Admin/repo",
            "https://github.com/API/repo",
            "https://github.com/Root/repo"
        ]
        
        for url in blocked_urls:
            with pytest.raises(ValueError, match="Repository owner contains blocked pattern"):
                validate_repository_url(url)


@pytest.mark.unit
@pytest.mark.security
class TestFilterSensitiveLogs:
    """Test filter_sensitive_logs function."""

    def test_filter_tokens(self):
        """Test filtering of tokens and API keys."""
        test_cases = [
            ("Using token=abc123def456", "Using token=[REDACTED]"),
            ("API key=secret123&other=value", "API key=[REDACTED]&other=value"),
            ("Secret=mysecret token=abc123", "Secret=[REDACTED] token=[REDACTED]"),
        ]
        
        for original, expected in test_cases:
            result = filter_sensitive_logs(original)
            assert result == expected

    def test_filter_authorization_headers(self):
        """Test filtering of Authorization headers."""
        test_cases = [
            ("Authorization: Bearer abc123def456", "Authorization: Bearer [REDACTED]"),
            ("AUTHORIZATION: BEARER secret123", "Authorization: Bearer [REDACTED]"),
            ("authorization: bearer token123", "Authorization: Bearer [REDACTED]"),
        ]
        
        for original, expected in test_cases:
            result = filter_sensitive_logs(original)
            assert result == expected

    def test_filter_urls_with_params(self):
        """Test filtering of URLs with sensitive parameters."""
        test_cases = [
            ("GET https://api.github.com/repos?token=secret", "GET [URL_WITH_PARAMS_REDACTED]"),
            ("POST https://example.com/api?key=abc123&id=456", "POST [URL_WITH_PARAMS_REDACTED]"),
            ("Fetching from https://api.com/data?auth=token123", "Fetching from [URL_WITH_PARAMS_REDACTED]"),
        ]
        
        for original, expected in test_cases:
            result = filter_sensitive_logs(original)
            assert result == expected

    def test_preserve_clean_logs(self):
        """Test that clean log messages are preserved."""
        clean_messages = [
            "Successfully fetched PR data",
            "Processing 5 commits from repository",
            "Generated changelog for owner/repo",
            "GitHub API request completed successfully"
        ]
        
        for message in clean_messages:
            result = filter_sensitive_logs(message)
            assert result == message

    def test_multiple_sensitive_patterns(self):
        """Test filtering of multiple sensitive patterns in one message."""
        original = "Authorization: Bearer secret123 requesting https://api.com/data?token=abc&key=def"
        result = filter_sensitive_logs(original)
        
        assert "secret123" not in result
        assert "token=abc" not in result
        assert "[REDACTED]" in result
        assert "[URL_WITH_PARAMS_REDACTED]" in result


@pytest.mark.unit
@pytest.mark.security
class TestShowPrivacyNotice:
    """Test show_privacy_notice function."""

    def test_privacy_notice_display(self):
        """Test that privacy notice is displayed correctly."""
        with patch('streamlit.expander') as mock_expander, \
             patch('streamlit.markdown') as mock_markdown, \
             patch('streamlit.checkbox', return_value=True) as mock_checkbox, \
             patch('streamlit.success') as mock_success:
            
            # Setup
            mock_expander_context = Mock()
            mock_expander.return_value.__enter__ = Mock(return_value=mock_expander_context)
            mock_expander.return_value.__exit__ = Mock(return_value=None)
            
            # Execute
            result = show_privacy_notice()
            
            # Assert
            assert result is True
            mock_expander.assert_called_once_with("🔒 Privacy Notice - Please Read", expanded=False)
            mock_checkbox.assert_called_once()
            mock_success.assert_called_once_with("✅ Privacy consent granted")

    def test_privacy_notice_declined(self):
        """Test behavior when privacy notice is declined."""
        with patch('streamlit.expander') as mock_expander, \
             patch('streamlit.markdown') as mock_markdown, \
             patch('streamlit.checkbox', return_value=False) as mock_checkbox, \
             patch('streamlit.warning') as mock_warning:
            
            # Setup
            mock_expander_context = Mock()
            mock_expander.return_value.__enter__ = Mock(return_value=mock_expander_context)
            mock_expander.return_value.__exit__ = Mock(return_value=None)
            
            # Execute
            result = show_privacy_notice()
            
            # Assert
            assert result is False
            mock_checkbox.assert_called_once()
            mock_warning.assert_called_once_with("⚠️ Privacy consent required to proceed")

    def test_privacy_notice_content(self):
        """Test that privacy notice contains expected content."""
        with patch('streamlit.expander') as mock_expander, \
             patch('streamlit.markdown') as mock_markdown, \
             patch('streamlit.checkbox', return_value=True), \
             patch('streamlit.success'):
            
            # Setup
            mock_expander_context = Mock()
            mock_expander.return_value.__enter__ = Mock(return_value=mock_expander_context)
            mock_expander.return_value.__exit__ = Mock(return_value=None)
            
            # Execute
            show_privacy_notice()
            
            # Assert
            mock_markdown.assert_called_once()
            markdown_content = mock_markdown.call_args[0][0]
            
            # Check for key privacy notice elements
            assert "Data Processing Notice" in markdown_content
            assert "OpenAI's GPT-4 service" in markdown_content
            assert "No data is permanently stored" in markdown_content
            assert "GitHub API" in markdown_content
            assert "OpenAI API" in markdown_content
            assert "Your Rights" in markdown_content


@pytest.mark.unit
@pytest.mark.security
class TestSecurityIntegration:
    """Test security functions working together."""

    def test_full_sanitization_pipeline(self, malicious_input_samples):
        """Test complete sanitization pipeline."""
        for category, samples in malicious_input_samples.items():
            for sample in samples:
                # Test commit message sanitization
                sanitized_commit = sanitize_commit_message(sample)
                
                # Test API response sanitization
                api_data = {'message': sample, 'title': sample}
                sanitized_api = sanitize_api_response(api_data)
                
                # Test log filtering
                log_message = f"Processing: {sample}"
                filtered_log = filter_sensitive_logs(log_message)
                
                # Assert that dangerous content is removed
                dangerous_patterns = ['<script>', 'javascript:', 'DROP TABLE', 'SELECT *', '@', 'http']
                
                for pattern in dangerous_patterns:
                    if pattern in sample.lower():
                        assert pattern not in sanitized_commit.lower() or '[' in sanitized_commit
                        if 'message' in sanitized_api:
                            assert pattern not in str(sanitized_api['message']).lower() or '[' in str(sanitized_api['message'])

    def test_url_validation_security(self):
        """Test URL validation against various attack vectors."""
        malicious_urls = [
            "https://github.com/admin/../../../etc/passwd",
            "https://github.com/owner/repo?token=secret",
            "https://github.com/owner/repo#javascript:alert('xss')",
            "https://github.com/owner/repo\x00malicious",
            "javascript:alert('xss')//github.com/owner/repo"
        ]
        
        for url in malicious_urls:
            with pytest.raises(ValueError):
                validate_repository_url(url)

    def test_defense_in_depth(self):
        """Test that multiple security layers work together."""
        # Simulate a malicious payload that tries to bypass multiple filters
        malicious_data = {
            'title': '<script>alert("xss")</script>',
            'message': 'Contact admin@evil.com at server 192.168.1.1 with token abc123def456789012345678901234567890',
            'dangerous_field': 'payload',
            'url': 'https://evil.com/steal?data=sensitive'
        }
        
        # Apply all security measures
        sanitized_message = sanitize_commit_message(malicious_data['message'])
        sanitized_response = sanitize_api_response(malicious_data)
        filtered_log = filter_sensitive_logs(f"Processing {malicious_data['title']}")
        
        # Assert comprehensive protection
        assert '@evil.com' not in sanitized_message
        assert '192.168.1.1' not in sanitized_message
        assert 'abc123def456789012345678901234567890' not in sanitized_message
        assert 'dangerous_field' not in sanitized_response
        assert '<script>' not in str(sanitized_response.get('title', ''))
        assert 'alert' not in filtered_log or '[' in filtered_log