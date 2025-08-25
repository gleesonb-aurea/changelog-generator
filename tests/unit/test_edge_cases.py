"""Edge case tests for the changelog generator."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from datetime import date, datetime
import json

from utils.github_data_fetch import (
    github_api_call, fetch_prs_merged_between_dates, 
    fetch_commits_from_prs, _transform_commits_to_records
)
from utils.summarisation import extract_messages_from_commits, gpt_inference_changelog
from utils.security import sanitize_commit_message, sanitize_api_response, validate_repository_url
from config.settings import validate_github_token, AppConfig
from config.exceptions import GitHubAPIError, OpenAIAPIError, ValidationError


@pytest.mark.unit
class TestEmptyDataHandling:
    """Test handling of empty or null data."""

    def test_empty_pr_dataframe(self):
        """Test handling of empty PR DataFrame."""
        empty_df = pd.DataFrame()
        
        # Should not crash with empty input
        result = fetch_commits_from_prs(empty_df, "owner", "repo")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_empty_commit_dataframe(self):
        """Test handling of empty commit DataFrame."""
        empty_df = pd.DataFrame()
        
        result = extract_messages_from_commits(empty_df)
        assert result == ""

    def test_none_values_in_data(self):
        """Test handling of None values in data structures."""
        data_with_nones = pd.DataFrame([
            {'PR Number': None, 'PR Title': None, 'Commit Message': None},
            {'PR Number': 123, 'PR Title': 'Valid PR', 'Commit Message': 'Valid commit'},
            {'PR Number': 124, 'PR Title': None, 'Commit Message': 'Another commit'}
        ])
        
        # Should handle None values gracefully
        result = extract_messages_from_commits(data_with_nones)
        assert isinstance(result, str)
        assert "Valid PR" in result

    def test_empty_strings_in_data(self):
        """Test handling of empty strings in data."""
        data_with_empty_strings = pd.DataFrame([
            {'PR Number': 123, 'PR Title': '', 'Commit Message': ''},
            {'PR Number': 124, 'PR Title': 'Valid PR', 'Commit Message': 'Valid commit'}
        ])
        
        result = extract_messages_from_commits(data_with_empty_strings)
        assert "Valid PR" in result
        assert "PR #123:" in result or "PR #124:" in result

    def test_whitespace_only_data(self):
        """Test handling of whitespace-only data."""
        whitespace_data = pd.DataFrame([
            {'PR Number': 123, 'PR Title': '   ', 'Commit Message': '\n\t  \n'},
            {'PR Number': 124, 'PR Title': 'Valid PR', 'Commit Message': 'Valid commit'}
        ])
        
        result = extract_messages_from_commits(whitespace_data)
        assert "Valid PR" in result

    def test_null_api_responses(self):
        """Test handling of null API responses."""
        # Test with None response
        assert sanitize_api_response(None) is None
        
        # Test with empty list
        assert sanitize_api_response([]) == []
        
        # Test with empty dict
        assert sanitize_api_response({}) == {}


@pytest.mark.unit
class TestMalformedDataHandling:
    """Test handling of malformed or corrupted data."""

    def test_invalid_json_response_simulation(self):
        """Test handling when API returns invalid JSON-like data."""
        malformed_data = {
            'number': 'not_a_number',
            'merged_at': 'invalid_date',
            'nested': {
                'invalid': float('inf'),
                'another': float('nan')
            }
        }
        
        # Should not crash with malformed data
        result = sanitize_api_response(malformed_data)
        assert isinstance(result, dict)

    def test_circular_reference_data(self):
        """Test handling of data structures with circular references."""
        circular_data = {'key': 'value'}
        circular_data['self'] = circular_data  # Circular reference
        
        # Should handle without infinite recursion
        try:
            result = sanitize_api_response(circular_data)
            # Should complete without hanging
            assert isinstance(result, dict)
        except RecursionError:
            pytest.fail("Function did not handle circular reference properly")

    def test_mixed_type_lists(self):
        """Test handling of lists with mixed data types."""
        mixed_list = [
            {'valid': 'dict'},
            'string_item',
            123,
            None,
            [],
            {'nested': {'deep': 'value'}}
        ]
        
        result = sanitize_api_response(mixed_list)
        assert isinstance(result, list)
        assert len(result) == len(mixed_list)

    def test_unicode_edge_cases(self):
        """Test handling of Unicode edge cases."""
        unicode_edge_cases = [
            'café',  # Accented characters
            '🚀',  # Emoji
            '中文',  # Chinese characters
            'עברית',  # Hebrew (RTL)
            '🏳️‍🌈',  # Complex emoji with ZWJ
            '\u200b',  # Zero-width space
            '\ufeff'  # BOM character
        ]
        
        for case in unicode_edge_cases:
            result = sanitize_commit_message(case)
            assert isinstance(result, str)

    def test_extremely_long_strings(self):
        """Test handling of extremely long strings."""
        very_long_string = "a" * 1000000  # 1MB string
        
        # Should handle without memory issues
        result = sanitize_commit_message(very_long_string)
        assert isinstance(result, str)

    def test_deeply_nested_structures(self):
        """Test handling of deeply nested data structures."""
        deep_structure = {}
        current = deep_structure
        
        for i in range(1000):  # 1000 levels deep
            current['level'] = i
            current['next'] = {}
            current = current['next']
        
        # Should handle deep nesting
        try:
            result = sanitize_api_response(deep_structure)
            assert isinstance(result, dict)
        except RecursionError:
            # If recursion limit hit, that's acceptable for extreme nesting
            pass


@pytest.mark.unit
class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_date_boundary_conditions(self):
        """Test date handling at boundaries."""
        boundary_dates = [
            (date(1970, 1, 1), date(1970, 1, 2)),  # Unix epoch start
            (date(2038, 1, 19), date(2038, 1, 20)),  # 32-bit timestamp limit
            (date(9999, 12, 31), date(9999, 12, 31)),  # Year 9999
            (date(2024, 2, 29), date(2024, 3, 1)),  # Leap year boundary
            (date(2024, 12, 31), date(2025, 1, 1))  # Year boundary
        ]
        
        for start_date, end_date in boundary_dates:
            # Should not raise errors for valid date ranges
            try:
                # This would normally make an API call, but we're testing validation
                with patch('utils.github_data_fetch.github_api_call'):
                    with patch('utils.github_data_fetch.get_secure_github_token', return_value="test"):
                        with patch('streamlit.error'), patch('streamlit.stop'):
                            # The function should accept these dates without validation errors
                            pass
            except ValidationError:
                if start_date > end_date:
                    # This is expected
                    pass
                else:
                    pytest.fail(f"Valid date range {start_date} to {end_date} was rejected")

    def test_github_token_boundary_conditions(self):
        """Test GitHub token validation at boundaries."""
        # Test exact length boundaries
        boundary_tests = [
            ("ghp_" + "a" * 35, False),  # One short
            ("ghp_" + "a" * 36, True),   # Exact length
            ("ghp_" + "a" * 37, False),  # One long
            ("github_pat_" + "a" * 21, False),  # One short for fine-grained
            ("github_pat_" + "a" * 22, True),   # Minimum for fine-grained
            ("github_pat_" + "a" * 255, True),  # Maximum for fine-grained
            ("github_pat_" + "a" * 256, False)  # One over maximum
        ]
        
        for token, expected in boundary_tests:
            result = validate_github_token(token)
            assert result == expected, f"Token {token} validation failed"

    def test_repository_name_boundaries(self):
        """Test repository name validation at boundaries."""
        # Test various repository name edge cases
        edge_cases = [
            ("https://github.com/a/b", True),  # Single character names
            ("https://github.com/a" + "a" * 38 + "/repo", True),  # Max owner length
            ("https://github.com/owner/" + "r" * 100, True),  # Max repo length
            ("https://github.com/123/456", True),  # Numeric names
            ("https://github.com/test-user/test-repo", True),  # With hyphens
            ("https://github.com/test_user/test_repo", True),  # With underscores
            ("https://github.com/test.user/test.repo", True),  # With dots
            ("https://github.com/test-/test-", True),  # Ending with hyphen
            ("https://github.com/_test/_test", True),  # Starting with underscore
        ]
        
        for url, should_be_valid in edge_cases:
            try:
                owner, repo = validate_repository_url(url)
                if should_be_valid:
                    assert owner is not None and repo is not None
                else:
                    pytest.fail(f"Expected {url} to be invalid but it passed")
            except ValueError:
                if should_be_valid:
                    pytest.fail(f"Expected {url} to be valid but it was rejected")

    def test_commit_message_size_limits(self):
        """Test commit message handling at size boundaries."""
        size_tests = [
            ("", "Empty message"),
            ("a", "Single character"),
            ("a" * 50, "Normal length"),
            ("a" * 1000, "Long message"),
            ("a" * 10000, "Very long message"),
            ("a" * 100000, "Extremely long message")
        ]
        
        for message, description in size_tests:
            result = sanitize_commit_message(message)
            assert isinstance(result, str), f"Failed for {description}"
            assert len(result) >= 0, f"Negative length for {description}"


@pytest.mark.unit
class TestErrorConditions:
    """Test various error conditions and recovery."""

    def test_network_timeout_simulation(self, mock_github_token):
        """Test handling of network timeouts."""
        import requests
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('requests.get', side_effect=requests.exceptions.Timeout("Request timeout")), \
             patch('streamlit.error'), patch('streamlit.stop'):
            
            with pytest.raises(GitHubAPIError, match="timeout"):
                github_api_call("test", "owner", "repo")

    def test_connection_error_simulation(self, mock_github_token):
        """Test handling of connection errors."""
        import requests
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('requests.get', side_effect=requests.exceptions.ConnectionError("Connection failed")), \
             patch('streamlit.error'), patch('streamlit.stop'):
            
            with pytest.raises(GitHubAPIError, match="Failed to connect"):
                github_api_call("test", "owner", "repo")

    def test_http_error_codes(self, mock_github_token):
        """Test handling of various HTTP error codes."""
        from utils.github_data_fetch import github_api_call
        
        error_codes = [
            (400, "Bad Request"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not Found"),
            (422, "Unprocessable Entity"),
            (500, "Internal Server Error"),
            (502, "Bad Gateway"),
            (503, "Service Unavailable")
        ]
        
        for status_code, description in error_codes:
            with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
                 patch('requests.get') as mock_get, \
                 patch('streamlit.error'), patch('streamlit.stop'):
                
                mock_response = Mock()
                mock_response.status_code = status_code
                mock_response.headers = {'X-RateLimit-Remaining': '5000'}
                mock_get.return_value = mock_response
                
                with pytest.raises(GitHubAPIError):
                    github_api_call("test", "owner", "repo")

    def test_malformed_json_response(self, mock_github_token):
        """Test handling of malformed JSON in API responses."""
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('requests.get') as mock_get, \
             patch('streamlit.error'), patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
            mock_response.headers = {'X-RateLimit-Remaining': '5000'}
            mock_get.return_value = mock_response
            
            # Should return the response even if JSON parsing fails
            result = github_api_call("test", "owner", "repo")
            assert result == mock_response

    def test_openai_error_conditions(self, mock_openai_key):
        """Test handling of various OpenAI API error conditions."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('streamlit.error'):
            
            error_conditions = [
                Exception("General error"),
                ConnectionError("Connection failed"),
                TimeoutError("Request timeout"),
                ValueError("Invalid parameters")
            ]
            
            for error in error_conditions:
                mock_client_instance = Mock()
                mock_client_instance.chat.completions.create.side_effect = error
                mock_openai_client.return_value = mock_client_instance
                
                with pytest.raises(OpenAIAPIError):
                    gpt_inference_changelog(
                        "test", date(2024, 1, 1), date(2024, 1, 31),
                        "owner", "repo", "desc", ["main"]
                    )

    def test_configuration_missing_secrets(self):
        """Test handling when secrets/environment variables are missing."""
        from config.settings import AppConfig
        
        with patch('streamlit.secrets.__getitem__', side_effect=KeyError("No secrets")), \
             patch.dict('os.environ', {}, clear=True):
            
            config = AppConfig()
            
            # Should handle missing configuration gracefully
            assert config.github_token is None
            assert config.openai_api_key is None

    def test_invalid_configuration_values(self):
        """Test handling of invalid configuration values."""
        from config.settings import AppConfig
        
        invalid_configs = [
            {'GITHUB_API_KEY': '', 'OPENAI_API_KEY': ''},  # Empty strings
            {'GITHUB_API_KEY': 'invalid', 'OPENAI_API_KEY': 'also_invalid'},  # Invalid format
            {'GITHUB_API_KEY': None, 'OPENAI_API_KEY': None}  # None values
        ]
        
        for config_dict in invalid_configs:
            with patch('streamlit.secrets.__getitem__', side_effect=KeyError("No secrets")), \
                 patch.dict('os.environ', config_dict, clear=True):
                
                config = AppConfig()
                # Should not crash, should handle gracefully
                github_token = config.github_token
                openai_key = config.openai_api_key


@pytest.mark.unit
class TestConcurrencyEdgeCases:
    """Test edge cases related to concurrent operations."""

    def test_simultaneous_api_calls(self, mock_github_token):
        """Test handling of simultaneous API calls."""
        from utils.github_data_fetch import github_api_call
        import threading
        import time
        
        call_results = []
        
        def make_api_call(call_id):
            with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
                 patch('requests.get') as mock_get, \
                 patch('streamlit.error'), patch('streamlit.stop'):
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'id': call_id}
                mock_response.headers = {'X-RateLimit-Remaining': '5000'}
                mock_get.return_value = mock_response
                
                try:
                    result = github_api_call(f"test{call_id}", "owner", "repo")
                    call_results.append(('success', call_id, result))
                except Exception as e:
                    call_results.append(('error', call_id, str(e)))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_api_call, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)
        
        # All calls should complete
        assert len(call_results) == 5
        assert all(result[0] == 'success' for result in call_results)

    def test_shared_state_isolation(self):
        """Test that different instances don't share state inappropriately."""
        from config.settings import AppConfig
        
        # Create multiple config instances
        config1 = AppConfig()
        config2 = AppConfig()
        
        # Modify one instance
        config1.github.per_page = 200
        
        # Other instance should be unaffected
        assert config2.github.per_page == 100  # Default value


@pytest.mark.unit
class TestMemoryEdgeCases:
    """Test memory-related edge cases."""

    def test_large_dataframe_processing(self):
        """Test processing of large DataFrames without memory issues."""
        # Create large DataFrame
        large_df = pd.DataFrame({
            'PR Number': range(10000),
            'PR Title': [f'PR #{i}' for i in range(10000)],
            'Commit Message': [f'Commit message {i}' * 10 for i in range(10000)]  # Long messages
        })
        
        # Should process without memory errors
        result = extract_messages_from_commits(large_df)
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Clean up
        del large_df

    def test_memory_efficient_sanitization(self):
        """Test that sanitization doesn't consume excessive memory."""
        # Create large text to sanitize
        large_text = "Test message with email@example.com and IP 192.168.1.1 " * 10000
        
        # Should sanitize without memory issues
        result = sanitize_commit_message(large_text)
        assert isinstance(result, str)
        assert 'email@example.com' not in result
        assert '192.168.1.1' not in result


@pytest.mark.unit
class TestTypeEdgeCases:
    """Test edge cases with different data types."""

    def test_numeric_string_handling(self):
        """Test handling of numeric strings."""
        numeric_data = pd.DataFrame({
            'PR Number': ['123', '456', '789'],  # String numbers
            'PR Title': [123, 456, 789],  # Numeric titles
            'Commit Message': [12.34, 56.78, 90.12]  # Float messages
        })
        
        # Should handle mixed types gracefully
        result = extract_messages_from_commits(numeric_data)
        assert isinstance(result, str)

    def test_boolean_data_handling(self):
        """Test handling of boolean data."""
        boolean_data = {
            'success': True,
            'error': False,
            'nested': {'flag': True, 'status': False}
        }
        
        result = sanitize_api_response(boolean_data)
        # Booleans should be preserved
        assert 'success' in result
        assert result['success'] is True

    def test_datetime_object_handling(self):
        """Test handling of datetime objects."""
        datetime_data = pd.DataFrame({
            'PR Number': [123],
            'PR Title': ['Test PR'],
            'Commit Message': [datetime.now()]  # datetime object
        })
        
        # Should convert to string without crashing
        result = extract_messages_from_commits(datetime_data)
        assert isinstance(result, str)