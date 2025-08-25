"""Unit tests for utils.github_data_fetch module."""

import pytest
import pandas as pd
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime

from utils.github_data_fetch import (
    github_api_call,
    fetch_commits_from_prs,
    fetch_commits_from_pr,
    fetch_prs_merged_between_dates,
    _fetch_pr_commits_with_retry,
    _transform_commits_to_records
)
from config.exceptions import GitHubAPIError, ValidationError
from conftest import MockResponse


@pytest.mark.unit
class TestGitHubApiCall:
    """Test github_api_call function."""

    def test_successful_api_call(self, mock_requests_get, mock_github_token):
        """Test successful API call."""
        # Setup
        expected_data = {"test": "data"}
        mock_response = MockResponse(expected_data)
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute
            response = github_api_call("pulls", "owner", "repo")
            
            # Assert
            assert response == mock_response
            mock_requests_get.assert_called_once()
            call_args = mock_requests_get.call_args
            assert "Bearer " + mock_github_token in call_args[1]["headers"]["Authorization"]

    def test_api_call_with_params(self, mock_requests_get, mock_github_token):
        """Test API call with parameters."""
        # Setup
        params = {"state": "closed", "per_page": 100}
        mock_response = MockResponse({"test": "data"})
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute
            github_api_call("pulls", "owner", "repo", params)
            
            # Assert
            call_args = mock_requests_get.call_args
            assert call_args[1]["params"] == params

    def test_rate_limit_exceeded(self, mock_requests_get, mock_github_token):
        """Test handling of rate limit exceeded."""
        # Setup
        mock_response = MockResponse({}, status_code=403, headers={
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': '1640995200'
        })
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.stop'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="Rate limit exceeded"):
                github_api_call("pulls", "owner", "repo")
            
            mock_error.assert_called()

    def test_rate_limit_warning(self, mock_requests_get, mock_github_token):
        """Test warning when rate limit is low."""
        # Setup
        mock_response = MockResponse({}, headers={'X-RateLimit-Remaining': '5'})
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.warning') as mock_warning, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute
            github_api_call("pulls", "owner", "repo")
            
            # Assert
            mock_warning.assert_called_with("GitHub API rate limit low: 5 requests remaining")

    def test_repository_not_found(self, mock_requests_get, mock_github_token):
        """Test handling of repository not found."""
        # Setup
        mock_response = MockResponse({}, status_code=404)
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="Repository .* not found"):
                github_api_call("pulls", "owner", "repo")

    def test_unauthorized_access(self, mock_requests_get, mock_github_token):
        """Test handling of unauthorized access."""
        # Setup
        mock_response = MockResponse({}, status_code=401)
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="GitHub token is invalid"):
                github_api_call("pulls", "owner", "repo")

    def test_timeout_error(self, mock_requests_get, mock_github_token):
        """Test handling of timeout errors."""
        # Setup
        mock_requests_get.side_effect = requests.exceptions.Timeout()
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="GitHub API request timeout"):
                github_api_call("pulls", "owner", "repo")

    def test_connection_error(self, mock_requests_get, mock_github_token):
        """Test handling of connection errors."""
        # Setup
        mock_requests_get.side_effect = requests.exceptions.ConnectionError()
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="Failed to connect to GitHub API"):
                github_api_call("pulls", "owner", "repo")

    def test_no_github_token(self):
        """Test behavior when GitHub token is not available."""
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=None), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.stop') as mock_stop:
            
            # Execute
            github_api_call("pulls", "owner", "repo")
            
            # Assert
            mock_error.assert_called_with("GitHub token is required")
            mock_stop.assert_called_once()


@pytest.mark.unit
class TestFetchCommitsFromPr:
    """Test fetch_commits_from_pr function."""

    def test_successful_commit_fetch(self, mock_commit_api_response):
        """Test successful commit fetching."""
        with patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=mock_commit_api_response):
            
            mock_response = Mock()
            mock_response.json.return_value = mock_commit_api_response
            mock_api_call.return_value = mock_response
            
            # Execute
            result = fetch_commits_from_pr(123, "owner", "repo")
            
            # Assert
            assert result == mock_commit_api_response
            mock_api_call.assert_called_once_with("pulls/123/commits", "owner", "repo")

    def test_github_api_error(self):
        """Test handling of GitHub API errors."""
        with patch('utils.github_data_fetch.github_api_call', side_effect=GitHubAPIError("API Error")):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError):
                fetch_commits_from_pr(123, "owner", "repo")

    def test_processing_error(self):
        """Test handling of processing errors."""
        with patch('utils.github_data_fetch.github_api_call') as mock_api_call:
            mock_response = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_api_call.return_value = mock_response
            
            # Execute
            result = fetch_commits_from_pr(123, "owner", "repo")
            
            # Assert
            assert result is None


@pytest.mark.unit
class TestFetchPrsMergedBetweenDates:
    """Test fetch_prs_merged_between_dates function."""

    def test_successful_pr_fetch(self, mock_github_api_response, date_range):
        """Test successful PR fetching."""
        with patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=mock_github_api_response):
            
            mock_response = Mock()
            mock_response.json.return_value = mock_github_api_response
            mock_api_call.return_value = mock_response
            
            # Execute
            df, description = fetch_prs_merged_between_dates(
                "owner", "repo", date_range['start_date'], date_range['end_date']
            )
            
            # Assert
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2  # Both PRs should be in date range
            assert description == "Test repository for changelog generation"

    def test_invalid_date_range(self):
        """Test validation of date range."""
        start_date = date(2024, 1, 31)
        end_date = date(2024, 1, 1)
        
        # Execute & Assert
        with pytest.raises(ValidationError, match="Start date must be before end date"):
            fetch_prs_merged_between_dates("owner", "repo", start_date, end_date)

    def test_empty_response(self):
        """Test handling of empty response."""
        with patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=[]):
            
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_api_call.return_value = mock_response
            
            # Execute
            df, description = fetch_prs_merged_between_dates(
                "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
            )
            
            # Assert
            assert df.empty
            assert description == ""

    def test_no_merged_prs(self):
        """Test handling when no PRs are merged."""
        # Create PRs without merged_at
        unmerged_prs = [
            {
                'number': 123,
                'title': 'Open PR',
                'merged_at': None,
                'state': 'open'
            }
        ]
        
        with patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=unmerged_prs):
            
            mock_response = Mock()
            mock_response.json.return_value = unmerged_prs
            mock_api_call.return_value = mock_response
            
            # Execute
            df, description = fetch_prs_merged_between_dates(
                "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
            )
            
            # Assert
            assert df.empty

    def test_date_filtering(self):
        """Test date range filtering."""
        prs_with_dates = [
            {
                'number': 123,
                'title': 'In range PR',
                'merged_at': '2024-01-15T10:30:00Z',
                'head': {'repo': {'description': 'Test'}}
            },
            {
                'number': 124,
                'title': 'Out of range PR',
                'merged_at': '2024-02-15T10:30:00Z',
                'head': {'repo': {'description': 'Test'}}
            }
        ]
        
        with patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=prs_with_dates):
            
            mock_response = Mock()
            mock_response.json.return_value = prs_with_dates
            mock_api_call.return_value = mock_response
            
            # Execute
            df, _ = fetch_prs_merged_between_dates(
                "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
            )
            
            # Assert
            assert len(df) == 1
            assert df.iloc[0]['number'] == 123


@pytest.mark.unit
class TestFetchCommitsFromPrs:
    """Test fetch_commits_from_prs function."""

    def test_successful_commits_fetch(self, sample_pr_data):
        """Test successful commits fetching from multiple PRs."""
        mock_commits = [
            {'sha': 'abc123', 'commit': {'message': 'Test commit 1'}},
            {'sha': 'def456', 'commit': {'message': 'Test commit 2'}}
        ]
        
        with patch('utils.github_data_fetch._fetch_pr_commits_with_retry', return_value=mock_commits), \
             patch('utils.github_data_fetch._transform_commits_to_records') as mock_transform:
            
            mock_transform.return_value = [
                {'PR Number': 123, 'Commit Message': 'Test commit 1'},
                {'PR Number': 123, 'Commit Message': 'Test commit 2'}
            ]
            
            # Execute
            result = fetch_commits_from_prs(sample_pr_data, "owner", "repo")
            
            # Assert
            assert isinstance(result, pd.DataFrame)
            assert mock_transform.call_count == len(sample_pr_data)

    def test_pr_commit_fetch_failure(self, sample_pr_data):
        """Test handling of PR commit fetch failures."""
        with patch('utils.github_data_fetch._fetch_pr_commits_with_retry', side_effect=GitHubAPIError("API Error")), \
             patch('streamlit.warning') as mock_warning:
            
            # Execute
            result = fetch_commits_from_prs(sample_pr_data, "owner", "repo")
            
            # Assert
            assert isinstance(result, pd.DataFrame)
            assert result.empty
            assert mock_warning.call_count == len(sample_pr_data)

    def test_unexpected_error_handling(self, sample_pr_data):
        """Test handling of unexpected errors."""
        with patch('utils.github_data_fetch._fetch_pr_commits_with_retry', side_effect=ValueError("Unexpected error")), \
             patch('streamlit.warning') as mock_warning:
            
            # Execute
            result = fetch_commits_from_prs(sample_pr_data, "owner", "repo")
            
            # Assert
            assert isinstance(result, pd.DataFrame)
            assert result.empty
            assert mock_warning.call_count == len(sample_pr_data)


@pytest.mark.unit
class TestFetchPrCommitsWithRetry:
    """Test _fetch_pr_commits_with_retry function."""

    def test_successful_first_attempt(self):
        """Test successful fetch on first attempt."""
        mock_commits = [{'sha': 'abc123', 'commit': {'message': 'Test'}}]
        
        with patch('utils.github_data_fetch.fetch_commits_from_pr', return_value=mock_commits):
            
            # Execute
            result = _fetch_pr_commits_with_retry(123, "owner", "repo", 3)
            
            # Assert
            assert result == mock_commits

    def test_retry_on_github_api_error(self):
        """Test retry logic on GitHub API errors."""
        mock_commits = [{'sha': 'abc123', 'commit': {'message': 'Test'}}]
        
        with patch('utils.github_data_fetch.fetch_commits_from_pr') as mock_fetch, \
             patch('time.sleep'):
            
            # First call fails, second succeeds
            mock_fetch.side_effect = [GitHubAPIError("Rate limit"), mock_commits]
            
            # Execute
            result = _fetch_pr_commits_with_retry(123, "owner", "repo", 3)
            
            # Assert
            assert result == mock_commits
            assert mock_fetch.call_count == 2

    def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        with patch('utils.github_data_fetch.fetch_commits_from_pr', side_effect=GitHubAPIError("Persistent error")), \
             patch('time.sleep'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="Persistent error"):
                _fetch_pr_commits_with_retry(123, "owner", "repo", 2)

    def test_exponential_backoff(self):
        """Test exponential backoff in retry logic."""
        with patch('utils.github_data_fetch.fetch_commits_from_pr', side_effect=GitHubAPIError("Error")), \
             patch('time.sleep') as mock_sleep:
            
            try:
                _fetch_pr_commits_with_retry(123, "owner", "repo", 3)
            except GitHubAPIError:
                pass
            
            # Assert exponential backoff
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert len(sleep_calls) == 2  # 2 retry attempts
            assert sleep_calls[1] > sleep_calls[0]  # Second sleep should be longer


@pytest.mark.unit
class TestTransformCommitsToRecords:
    """Test _transform_commits_to_records function."""

    def test_successful_transformation(self):
        """Test successful commit transformation."""
        commits = [
            {'sha': 'abc123', 'commit': {'message': 'Fix bug'}},
            {'sha': 'def456', 'commit': {'message': 'Add feature'}}
        ]
        
        pr_row = pd.Series({'number': 123, 'title': 'Test PR'})
        
        with patch('utils.security.sanitize_commit_message', side_effect=lambda x: x):
            
            # Execute
            result = _transform_commits_to_records(commits, pr_row)
            
            # Assert
            assert len(result) == 2
            assert result[0]['PR Number'] == 123
            assert result[0]['PR Title'] == 'Test PR'
            assert result[0]['Commit SHA'] == 'abc123'
            assert result[0]['Commit Message'] == 'Fix bug'

    def test_skip_merge_commits(self):
        """Test that merge commits are skipped."""
        commits = [
            {'sha': 'abc123', 'commit': {'message': 'Fix bug'}},
            {'sha': 'def456', 'commit': {'message': 'Merge branch "feature" into main'}}
        ]
        
        pr_row = pd.Series({'number': 123, 'title': 'Test PR'})
        
        with patch('utils.security.sanitize_commit_message', side_effect=lambda x: x):
            
            # Execute
            result = _transform_commits_to_records(commits, pr_row)
            
            # Assert
            assert len(result) == 1
            assert result[0]['Commit Message'] == 'Fix bug'

    def test_invalid_commit_format(self):
        """Test handling of invalid commit format."""
        commits = [
            {'sha': 'abc123', 'commit': {'message': 'Valid commit'}},
            "invalid_commit_format",  # Invalid format
            {'sha': 'def456'}  # Missing commit data
        ]
        
        pr_row = pd.Series({'number': 123, 'title': 'Test PR'})
        
        with patch('utils.security.sanitize_commit_message', side_effect=lambda x: x):
            
            # Execute
            result = _transform_commits_to_records(commits, pr_row)
            
            # Assert
            assert len(result) == 1
            assert result[0]['Commit Message'] == 'Valid commit'

    def test_message_sanitization(self):
        """Test that commit messages are properly sanitized."""
        commits = [
            {'sha': 'abc123', 'commit': {'message': 'Commit with email@example.com'}}
        ]
        
        pr_row = pd.Series({'number': 123, 'title': 'Test PR'})
        
        with patch('utils.security.sanitize_commit_message', return_value='Commit with [EMAIL_REMOVED]') as mock_sanitize:
            
            # Execute
            result = _transform_commits_to_records(commits, pr_row)
            
            # Assert
            mock_sanitize.assert_called_once_with('Commit with email@example.com')
            assert result[0]['Commit Message'] == 'Commit with [EMAIL_REMOVED]'


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_json_response(self, mock_requests_get, mock_github_token):
        """Test handling of malformed JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_requests_get.return_value = mock_response
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # This should not raise an exception at the API call level
            response = github_api_call("pulls", "owner", "repo")
            assert response == mock_response

    def test_empty_commit_list(self):
        """Test handling of empty commit list."""
        pr_row = pd.Series({'number': 123, 'title': 'Test PR'})
        result = _transform_commits_to_records([], pr_row)
        assert result == []

    def test_none_commit_data(self):
        """Test handling of None commit data."""
        commits = [None, {'sha': 'abc123', 'commit': {'message': 'Valid'}}]
        pr_row = pd.Series({'number': 123, 'title': 'Test PR'})
        
        with patch('utils.security.sanitize_commit_message', side_effect=lambda x: x):
            result = _transform_commits_to_records(commits, pr_row)
            
        assert len(result) == 1
        assert result[0]['Commit Message'] == 'Valid'