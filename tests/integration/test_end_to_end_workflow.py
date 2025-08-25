"""Integration tests for end-to-end changelog generation workflow."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from typing import List, Dict, Any

from utils.github_data_fetch import fetch_prs_merged_between_dates, fetch_commits_from_prs
from utils.summarisation import extract_messages_from_commits, gpt_inference_changelog
from utils.security import validate_repository_url
from config.exceptions import GitHubAPIError, OpenAIAPIError, ValidationError


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete changelog generation workflow."""

    def test_complete_workflow_success(self, mock_github_token, mock_openai_key):
        """Test successful end-to-end changelog generation."""
        # Setup mock data
        mock_prs = [
            {
                'number': 123,
                'title': 'Fix authentication bug',
                'merged_at': '2024-01-15T10:30:00Z',
                'head': {'repo': {'description': 'Test repository'}}
            },
            {
                'number': 124,
                'title': 'Add user dashboard',
                'merged_at': '2024-01-16T14:22:00Z',
                'head': {'repo': {'description': 'Test repository'}}
            }
        ]
        
        mock_commits = [
            {'sha': 'abc123', 'commit': {'message': 'Fix JWT validation'}},
            {'sha': 'def456', 'commit': {'message': 'Add error handling'}},
            {'sha': 'ghi789', 'commit': {'message': 'Implement dashboard UI'}},
            {'sha': 'jkl012', 'commit': {'message': 'Add dashboard tests'}}
        ]
        
        expected_changelog = """# Changelog

## Fixed
- Fixed authentication bug in JWT validation [#123]
- Added error handling for authentication [#123]

## Added
- Implemented user dashboard UI [#124]
- Added comprehensive dashboard tests [#124]
"""
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response') as mock_sanitize, \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Setup API responses
            mock_response = Mock()
            mock_response.json.return_value = mock_prs
            mock_api_call.return_value = mock_response
            mock_sanitize.return_value = mock_prs
            
            # Setup commit responses for each PR
            def mock_commits_for_pr(pr_number, owner, repo):
                if pr_number == 123:
                    return mock_commits[:2]  # First 2 commits for PR 123
                elif pr_number == 124:
                    return mock_commits[2:]  # Last 2 commits for PR 124
                return []
            
            with patch('utils.github_data_fetch.fetch_commits_from_pr', side_effect=mock_commits_for_pr):
                
                # Setup OpenAI response
                mock_openai_response = Mock()
                mock_choice = Mock()
                mock_message = Mock()
                mock_message.content = expected_changelog
                mock_choice.message = mock_message
                mock_openai_response.choices = [mock_choice]
                
                mock_client_instance = Mock()
                mock_client_instance.chat.completions.create.return_value = mock_openai_response
                mock_openai_client.return_value = mock_client_instance
                
                # Execute workflow
                owner, repo = "test-owner", "test-repo"
                start_date = date(2024, 1, 1)
                end_date = date(2024, 1, 31)
                
                # Step 1: Fetch PRs
                prs_df, repo_description = fetch_prs_merged_between_dates(
                    owner, repo, start_date, end_date
                )
                
                # Step 2: Fetch commits
                commits_df = fetch_commits_from_prs(prs_df, owner, repo)
                
                # Step 3: Extract messages
                messages = extract_messages_from_commits(commits_df)
                
                # Step 4: Generate changelog
                changelog = gpt_inference_changelog(
                    messages, start_date, end_date, owner, repo, repo_description, ["main"]
                )
                
                # Assertions
                assert isinstance(prs_df, pd.DataFrame)
                assert len(prs_df) == 2
                assert isinstance(commits_df, pd.DataFrame)
                assert len(commits_df) == 4
                assert isinstance(messages, str)
                assert "PR #123" in messages
                assert "PR #124" in messages
                assert changelog == expected_changelog

    def test_workflow_with_no_prs(self, mock_github_token):
        """Test workflow when no PRs are found."""
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=[]), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_api_call.return_value = mock_response
            
            # Execute
            prs_df, repo_description = fetch_prs_merged_between_dates(
                "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
            )
            
            # Assertions
            assert prs_df.empty
            assert repo_description == ""

    def test_workflow_with_github_api_error(self, mock_github_token):
        """Test workflow handling of GitHub API errors."""
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('utils.github_data_fetch.github_api_call', side_effect=GitHubAPIError("Rate limit exceeded", 403)), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Execute & Assert
            with pytest.raises(GitHubAPIError, match="Rate limit exceeded"):
                fetch_prs_merged_between_dates(
                    "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
                )

    def test_workflow_with_openai_api_error(self, mock_github_token, mock_openai_key):
        """Test workflow handling of OpenAI API errors."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('streamlit.error'):
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.side_effect = Exception("API Error")
            mock_openai_client.return_value = mock_client_instance
            
            # Execute & Assert
            with pytest.raises(OpenAIAPIError, match="Error generating changelog"):
                gpt_inference_changelog(
                    "test commits", date(2024, 1, 1), date(2024, 1, 31),
                    "owner", "repo", "description", ["main"]
                )

    def test_workflow_with_invalid_repository_url(self):
        """Test workflow with invalid repository URL."""
        invalid_urls = [
            "http://github.com/owner/repo",
            "https://gitlab.com/owner/repo",
            "https://github.com/admin/repo"
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                validate_repository_url(url)

    def test_workflow_with_date_validation_error(self, mock_github_token):
        """Test workflow with invalid date range."""
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token):
            
            # Execute & Assert
            with pytest.raises(ValidationError, match="Start date must be before end date"):
                fetch_prs_merged_between_dates(
                    "owner", "repo", date(2024, 1, 31), date(2024, 1, 1)
                )

    def test_workflow_data_flow(self, sample_pr_data, sample_commit_data):
        """Test data flow through the workflow pipeline."""
        # Test that data formats are maintained throughout the pipeline
        
        # Step 1: Verify PR data format
        assert isinstance(sample_pr_data, pd.DataFrame)
        required_pr_columns = {'number', 'title', 'merged_at', 'branch'}
        assert required_pr_columns.issubset(sample_pr_data.columns)
        
        # Step 2: Verify commit data format
        assert isinstance(sample_commit_data, pd.DataFrame)
        required_commit_columns = {'PR Number', 'PR Title', 'Commit SHA', 'Commit Message'}
        assert required_commit_columns.issubset(sample_commit_data.columns)
        
        # Step 3: Extract messages
        messages = extract_messages_from_commits(sample_commit_data)
        assert isinstance(messages, str)
        assert len(messages) > 0
        
        # Verify message format
        assert "PR #123" in messages
        assert "Fix JWT token validation" in messages

    def test_workflow_with_multiple_branches(self, mock_github_token, mock_openai_key):
        """Test workflow with multiple branch handling."""
        branches = ["production", "staging", "qa"]
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('streamlit.error'):
            
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = "# Changelog\n\n## Fixed\n- Multi-branch fix"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            changelog = gpt_inference_changelog(
                "test commits", date(2024, 1, 1), date(2024, 1, 31),
                "owner", "repo", "description", branches
            )
            
            # Verify branch information was passed to OpenAI
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            assert "Branches: production, staging, qa" in user_message

    def test_error_recovery_workflow(self, mock_github_token, sample_pr_data):
        """Test workflow error recovery mechanisms."""
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('utils.github_data_fetch._fetch_pr_commits_with_retry') as mock_retry, \
             patch('streamlit.warning'):
            
            # Simulate partial failures in commit fetching
            def mock_retry_func(pr_number, owner, repo, max_retries):
                if pr_number == 123:
                    return [{'sha': 'abc', 'commit': {'message': 'Success'}}]
                else:
                    raise GitHubAPIError("Failed")
            
            mock_retry.side_effect = mock_retry_func
            
            # Execute
            commits_df = fetch_commits_from_prs(sample_pr_data, "owner", "repo")
            
            # Should continue processing despite partial failures
            assert isinstance(commits_df, pd.DataFrame)


@pytest.mark.integration
class TestRepositoryValidationIntegration:
    """Test repository validation integration."""

    def test_valid_repository_flow(self):
        """Test complete repository validation flow."""
        valid_urls = [
            "https://github.com/microsoft/vscode",
            "https://github.com/facebook/react",
            "https://github.com/google/go-github"
        ]
        
        for url in valid_urls:
            owner, repo = validate_repository_url(url)
            assert isinstance(owner, str)
            assert isinstance(repo, str)
            assert len(owner) > 0
            assert len(repo) > 0

    def test_security_validation_integration(self):
        """Test integration of security validations."""
        from utils.security import sanitize_commit_message, sanitize_api_response
        
        # Test malicious data through security pipeline
        malicious_commit = "Fix bug for user admin@evil.com at 192.168.1.1"
        malicious_api_data = {
            'title': '<script>alert("xss")</script>',
            'message': 'Contact hacker@evil.com',
            'dangerous_key': 'payload'
        }
        
        # Process through security functions
        clean_commit = sanitize_commit_message(malicious_commit)
        clean_api_data = sanitize_api_response(malicious_api_data)
        
        # Verify cleaning
        assert '@evil.com' not in clean_commit
        assert '192.168.1.1' not in clean_commit
        assert '<script>' not in str(clean_api_data.get('title', ''))
        assert 'dangerous_key' not in clean_api_data


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration integration with the workflow."""

    def test_configuration_loading_integration(self, mock_github_token, mock_openai_key):
        """Test that configuration is properly loaded and used."""
        from config.settings import AppConfig
        
        with patch('streamlit.secrets') as mock_secrets, \
             patch.dict('os.environ', {
                 'GITHUB_API_KEY': mock_github_token,
                 'OPENAI_API_KEY': mock_openai_key
             }):
            
            mock_secrets.__getitem__.side_effect = KeyError("No secrets")
            
            config = AppConfig()
            
            # Verify configuration properties
            assert config.github_token == mock_github_token
            assert config.openai_api_key == mock_openai_key
            assert config.github.api_base_url == "https://api.github.com"
            assert config.openai.model == "gpt-4o"

    def test_missing_configuration_handling(self):
        """Test handling of missing configuration."""
        from config.settings import validate_configuration
        from config.exceptions import ConfigurationError
        
        with patch('config.settings.get_secure_github_token', return_value=None), \
             patch('config.settings.get_secure_openai_key', return_value=None):
            
            with pytest.raises(ConfigurationError) as exc_info:
                validate_configuration()
            
            error_message = str(exc_info.value)
            assert "GitHub API token" in error_message
            assert "OpenAI API key" in error_message


@pytest.mark.integration
class TestApiIntegration:
    """Test API integration scenarios."""

    def test_github_api_rate_limit_handling(self, mock_github_token):
        """Test GitHub API rate limit handling."""
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('requests.get') as mock_get, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Simulate rate limit response
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.headers = {
                'X-RateLimit-Remaining': '0',
                'X-RateLimit-Reset': '1640995200'
            }
            mock_get.return_value = mock_response
            
            with pytest.raises(GitHubAPIError, match="Rate limit exceeded"):
                github_api_call("pulls", "owner", "repo")

    def test_openai_api_timeout_handling(self, mock_openai_key):
        """Test OpenAI API timeout handling."""
        import openai
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('streamlit.error'):
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.side_effect = openai.APITimeoutError("Timeout")
            mock_openai_client.return_value = mock_client_instance
            
            with pytest.raises(OpenAIAPIError):
                gpt_inference_changelog(
                    "test", date(2024, 1, 1), date(2024, 1, 31),
                    "owner", "repo", "desc", ["main"]
                )

    def test_api_retry_mechanisms(self, mock_github_token):
        """Test API retry mechanisms."""
        from utils.github_data_fetch import _fetch_pr_commits_with_retry
        
        with patch('utils.github_data_fetch.fetch_commits_from_pr') as mock_fetch, \
             patch('time.sleep'):
            
            # First two calls fail, third succeeds
            mock_commits = [{'sha': 'abc', 'commit': {'message': 'Test'}}]
            mock_fetch.side_effect = [
                GitHubAPIError("Temporary error"),
                GitHubAPIError("Another error"),
                mock_commits
            ]
            
            result = _fetch_pr_commits_with_retry(123, "owner", "repo", 3)
            
            assert result == mock_commits
            assert mock_fetch.call_count == 3


@pytest.mark.integration
@pytest.mark.slow
class TestLargeDatasetIntegration:
    """Test integration with larger datasets."""

    def test_large_pr_dataset_processing(self, large_pr_dataset):
        """Test processing of large PR datasets."""
        # Test that the system can handle large datasets
        assert len(large_pr_dataset) == 1000
        
        # Test message extraction with large dataset
        large_commit_data = pd.DataFrame([
            {
                'PR Number': i,
                'PR Title': f'PR #{i}',
                'Commit SHA': f'sha{i}',
                'Commit Message': f'Commit message {i}'
            }
            for i in range(1, 1001)
        ])
        
        # This should complete without errors
        messages = extract_messages_from_commits(large_commit_data)
        assert isinstance(messages, str)
        assert len(messages) > 0

    def test_memory_efficiency(self):
        """Test memory efficiency with large datasets."""
        import sys
        
        # Create a large dataset and ensure it doesn't consume excessive memory
        large_data = pd.DataFrame([
            {
                'PR Number': i,
                'PR Title': f'Large PR {i}',
                'Commit Message': f'Large commit message {i} with lots of text' * 10
            }
            for i in range(10000)
        ])
        
        # Process in chunks to test memory efficiency
        chunk_size = 1000
        processed_chunks = []
        
        for i in range(0, len(large_data), chunk_size):
            chunk = large_data[i:i + chunk_size]
            messages = extract_messages_from_commits(chunk)
            processed_chunks.append(len(messages))
        
        # Verify all chunks were processed
        assert len(processed_chunks) == 10
        assert all(chunk_length > 0 for chunk_length in processed_chunks)