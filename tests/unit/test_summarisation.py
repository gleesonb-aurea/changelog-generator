"""Unit tests for utils.summarisation module."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import date

from utils.summarisation import (
    extract_messages_from_commits,
    gpt_inference_changelog
)
from config.exceptions import OpenAIAPIError


@pytest.mark.unit
class TestExtractMessagesFromCommits:
    """Test extract_messages_from_commits function."""

    def test_successful_message_extraction(self, sample_commit_data):
        """Test successful extraction of commit messages."""
        # Execute
        result = extract_messages_from_commits(sample_commit_data)
        
        # Assert
        assert isinstance(result, str)
        assert "PR #123: Fix authentication bug" in result
        assert "Fix JWT token validation" in result
        assert "Add error handling for expired tokens" in result
        assert "PR #124: Add new feature" in result
        assert "Implement user profile dashboard" in result

    def test_empty_dataframe(self):
        """Test handling of empty commit DataFrame."""
        # Setup
        empty_df = pd.DataFrame()
        
        # Execute
        result = extract_messages_from_commits(empty_df)
        
        # Assert
        assert result == ""

    def test_skip_merge_commits(self):
        """Test that merge commits are skipped."""
        # Setup
        commit_data = pd.DataFrame([
            {
                'PR Number': 123,
                'PR Title': 'Test PR',
                'Commit SHA': 'abc123',
                'Commit Message': 'Fix authentication bug'
            },
            {
                'PR Number': 123,
                'PR Title': 'Test PR',
                'Commit SHA': 'def456',
                'Commit Message': 'Merge branch "feature" into main'
            },
            {
                'PR Number': 124,
                'PR Title': 'Another PR',
                'Commit SHA': 'ghi789',
                'Commit Message': 'Add new feature'
            }
        ])
        
        # Execute
        result = extract_messages_from_commits(commit_data)
        
        # Assert
        assert "Merge branch" not in result
        assert "Fix authentication bug" in result
        assert "Add new feature" in result

    def test_group_commits_by_pr(self):
        """Test that commits are properly grouped by PR."""
        # Setup
        commit_data = pd.DataFrame([
            {
                'PR Number': 123,
                'PR Title': 'Fix bugs',
                'Commit SHA': 'abc123',
                'Commit Message': 'Fix bug 1'
            },
            {
                'PR Number': 123,
                'PR Title': 'Fix bugs',
                'Commit SHA': 'def456',
                'Commit Message': 'Fix bug 2'
            },
            {
                'PR Number': 124,
                'PR Title': 'Add feature',
                'Commit SHA': 'ghi789',
                'Commit Message': 'Implement feature'
            }
        ])
        
        # Execute
        result = extract_messages_from_commits(commit_data)
        
        # Assert
        lines = result.split('\n')
        pr_123_section = [line for line in lines if 'PR #123' in line or 'Fix bug' in line]
        pr_124_section = [line for line in lines if 'PR #124' in line or 'Implement feature' in line]
        
        assert len(pr_123_section) == 3  # PR title + 2 commits
        assert len(pr_124_section) == 2  # PR title + 1 commit
        assert any("PR #123: Fix bugs" in line for line in pr_123_section)
        assert any("- Fix bug 1" in line for line in pr_123_section)
        assert any("- Fix bug 2" in line for line in pr_123_section)

    def test_single_commit_pr(self):
        """Test PR with single commit."""
        # Setup
        commit_data = pd.DataFrame([
            {
                'PR Number': 123,
                'PR Title': 'Single commit PR',
                'Commit SHA': 'abc123',
                'Commit Message': 'Fix single bug'
            }
        ])
        
        # Execute
        result = extract_messages_from_commits(commit_data)
        
        # Assert
        expected_lines = [
            "PR #123: Single commit PR",
            "- Fix single bug"
        ]
        for line in expected_lines:
            assert line in result

    def test_multiple_prs_formatting(self):
        """Test formatting of multiple PRs."""
        # Setup
        commit_data = pd.DataFrame([
            {
                'PR Number': 123,
                'PR Title': 'First PR',
                'Commit SHA': 'abc123',
                'Commit Message': 'First commit'
            },
            {
                'PR Number': 124,
                'PR Title': 'Second PR',
                'Commit SHA': 'def456',
                'Commit Message': 'Second commit'
            }
        ])
        
        # Execute
        result = extract_messages_from_commits(commit_data)
        
        # Assert
        sections = result.split('\n\n')  # PRs are separated by double newlines
        assert len(sections) == 2
        assert "PR #123: First PR" in sections[0]
        assert "PR #124: Second PR" in sections[1]


@pytest.mark.unit
class TestGptInferenceChangelog:
    """Test gpt_inference_changelog function."""

    def test_successful_changelog_generation(self, mock_openai_response, mock_openai_key):
        """Test successful changelog generation."""
        # Setup
        commits = "PR #123: Fix authentication bug\n- Fix JWT token validation"
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            result = gpt_inference_changelog(
                commits, start_date, end_date, "owner", "repo", "Test repo", ["main"]
            )
            
            # Assert
            assert result is not None
            assert "# Changelog" in result
            assert "Fixed authentication bug" in result
            mock_client_instance.chat.completions.create.assert_called_once()

    def test_multiple_branches_handling(self, mock_openai_response, mock_openai_key):
        """Test handling of multiple branches."""
        # Setup
        commits = "PR #123: Fix bug\n- Fix authentication"
        branches = ["production", "staging", "qa"]
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            gpt_inference_changelog(
                commits, date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "Test repo", branches
            )
            
            # Assert
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            assert "Branches: production, staging, qa" in user_message

    def test_single_branch_handling(self, mock_openai_response, mock_openai_key):
        """Test handling of single branch."""
        # Setup
        commits = "PR #123: Fix bug\n- Fix authentication"
        branch = "main"
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            gpt_inference_changelog(
                commits, date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "Test repo", branch
            )
            
            # Assert
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            assert "Branches: main" in user_message

    def test_no_openai_key(self):
        """Test behavior when OpenAI API key is not available."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=None), \
             patch('streamlit.error') as mock_error:
            
            # Execute
            result = gpt_inference_changelog(
                "commits", date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "description", ["main"]
            )
            
            # Assert
            assert result is None
            mock_error.assert_called_with("OpenAI API key is required")

    def test_openai_api_error(self, mock_openai_key):
        """Test handling of OpenAI API errors."""
        # Setup
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error') as mock_error, \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.side_effect = Exception("API Error")
            mock_openai_client.return_value = mock_client_instance
            
            # Execute & Assert
            with pytest.raises(OpenAIAPIError, match="Error generating changelog"):
                gpt_inference_changelog(
                    "commits", date(2024, 1, 1), date(2024, 1, 31), 
                    "owner", "repo", "description", ["main"]
                )
            
            mock_error.assert_called()

    def test_empty_openai_response(self, mock_openai_key):
        """Test handling of empty OpenAI response."""
        # Setup
        mock_response = Mock()
        mock_response.choices = []
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute & Assert
            with pytest.raises(OpenAIAPIError, match="No response from OpenAI API"):
                gpt_inference_changelog(
                    "commits", date(2024, 1, 1), date(2024, 1, 31), 
                    "owner", "repo", "description", ["main"]
                )

    def test_none_content_response(self, mock_openai_key):
        """Test handling of None content in OpenAI response."""
        # Setup
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = None
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute & Assert
            with pytest.raises(OpenAIAPIError, match="Empty response from OpenAI API"):
                gpt_inference_changelog(
                    "commits", date(2024, 1, 1), date(2024, 1, 31), 
                    "owner", "repo", "description", ["main"]
                )

    def test_system_prompt_format(self, mock_openai_response, mock_openai_key):
        """Test that system prompt is properly formatted."""
        # Setup
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            gpt_inference_changelog(
                "commits", date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "description", ["main"]
            )
            
            # Assert
            call_args = mock_client_instance.chat.completions.create.call_args
            messages = call_args[1]['messages']
            
            assert len(messages) == 2
            assert messages[0]['role'] == 'system'
            assert messages[1]['role'] == 'user'
            
            system_content = messages[0]['content']
            assert "Added, Changed, Deprecated, Removed, Fixed, Security" in system_content
            assert "PR numbers as links" in system_content
            assert "user-facing changes" in system_content

    def test_user_prompt_format(self, mock_openai_response, mock_openai_key):
        """Test that user prompt is properly formatted."""
        # Setup
        commits = "PR #123: Test PR\n- Test commit"
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        owner = "test-owner"
        repo = "test-repo"
        description = "Test repository description"
        branches = ["production", "staging"]
        
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            gpt_inference_changelog(
                commits, start_date, end_date, owner, repo, description, branches
            )
            
            # Assert
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            
            assert f"Generate a changelog for {owner}/{repo}" in user_message
            assert f"({description})" in user_message
            assert f"Time period: {start_date} to {end_date}" in user_message
            assert "Branches: production, staging" in user_message
            assert "Commit messages:" in user_message
            assert commits in user_message

    def test_configuration_usage(self, mock_openai_response, mock_openai_key):
        """Test that OpenAI configuration is properly used."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('utils.summarisation.AppConfig') as mock_config:
            
            # Setup mock config
            mock_config_instance = Mock()
            mock_config_instance.openai.model = "gpt-4o"
            mock_config_instance.openai.temperature = 0.7
            mock_config_instance.openai.max_tokens = 2048
            mock_config_instance.openai.timeout = 60
            mock_config.return_value = mock_config_instance
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            gpt_inference_changelog(
                "commits", date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "description", ["main"]
            )
            
            # Assert
            call_args = mock_client_instance.chat.completions.create.call_args
            call_kwargs = call_args[1]
            
            assert call_kwargs['model'] == "gpt-4o"
            assert call_kwargs['temperature'] == 0.7
            assert call_kwargs['max_tokens'] == 2048
            assert call_kwargs['timeout'] == 60


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_commits_string(self, mock_openai_response, mock_openai_key):
        """Test handling of empty commits string."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            result = gpt_inference_changelog(
                "", date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "description", ["main"]
            )
            
            # Assert
            assert result is not None
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            assert "Commit messages:\n" in user_message

    def test_none_description(self, mock_openai_response, mock_openai_key):
        """Test handling of None repository description."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            result = gpt_inference_changelog(
                "commits", date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", None, ["main"]
            )
            
            # Assert
            assert result is not None
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            assert "(None)" in user_message

    def test_empty_branches_list(self, mock_openai_response, mock_openai_key):
        """Test handling of empty branches list."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('streamlit.error'), \
             patch('openai.OpenAI') as mock_openai_client:
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai_client.return_value = mock_client_instance
            
            # Execute
            result = gpt_inference_changelog(
                "commits", date(2024, 1, 1), date(2024, 1, 31), 
                "owner", "repo", "description", []
            )
            
            # Assert
            assert result is not None
            call_args = mock_client_instance.chat.completions.create.call_args
            user_message = call_args[1]['messages'][1]['content']
            assert "Branches:" in user_message

    def test_dataframe_with_missing_columns(self):
        """Test handling of DataFrame with missing columns."""
        # Setup DataFrame with missing columns
        incomplete_df = pd.DataFrame([
            {'PR Number': 123, 'Commit Message': 'Test commit'}
            # Missing PR Title, Commit SHA
        ])
        
        # This should not raise an exception
        result = extract_messages_from_commits(incomplete_df)
        
        # The function should handle missing columns gracefully
        assert isinstance(result, str)