"""Performance tests for the changelog generator."""

import pytest
import pandas as pd
import time
from unittest.mock import Mock, patch
from datetime import date, datetime
import gc

from utils.github_data_fetch import (
    fetch_prs_merged_between_dates,
    fetch_commits_from_prs,
    _transform_commits_to_records
)
from utils.summarisation import extract_messages_from_commits, gpt_inference_changelog
from utils.security import sanitize_commit_message, sanitize_api_response


@pytest.mark.performance
@pytest.mark.slow
class TestGitHubApiPerformance:
    """Test GitHub API performance."""

    def test_pr_fetching_performance(self, mock_github_token):
        """Test performance of PR fetching with large datasets."""
        # Generate large mock response
        large_pr_data = [
            {
                'number': i,
                'title': f'PR #{i}',
                'merged_at': f'2024-01-{(i % 28) + 1:02d}T10:30:00Z',
                'head': {'repo': {'description': 'Performance test repo'}}
            }
            for i in range(1, 1001)  # 1000 PRs
        ]
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=large_pr_data), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.json.return_value = large_pr_data
            mock_api_call.return_value = mock_response
            
            # Measure performance
            start_time = time.time()
            
            prs_df, _ = fetch_prs_merged_between_dates(
                "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Performance assertions
            assert processing_time < 5.0, f"PR processing took too long: {processing_time}s"
            assert len(prs_df) <= 1000
            assert isinstance(prs_df, pd.DataFrame)

    @pytest.mark.benchmark
    def test_commit_transformation_benchmark(self, benchmark):
        """Benchmark commit transformation performance."""
        # Generate test data
        commits = [
            {
                'sha': f'commit{i:06d}abc',
                'commit': {'message': f'Test commit message {i} with detailed description'}
            }
            for i in range(1000)
        ]
        
        pr_row = pd.Series({
            'number': 123,
            'title': 'Performance Test PR'
        })
        
        with patch('utils.security.sanitize_commit_message', side_effect=lambda x: x):
            # Benchmark the function
            result = benchmark(_transform_commits_to_records, commits, pr_row)
            
            # Verify results
            assert len(result) == 1000
            assert all('PR Number' in record for record in result)

    def test_api_rate_limiting_performance(self, mock_github_token):
        """Test performance under rate limiting constraints."""
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('requests.get') as mock_get, \
             patch('time.sleep') as mock_sleep, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            # Simulate rate limit headers
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {'X-RateLimit-Remaining': '10'}
            mock_get.return_value = mock_response
            
            # Multiple API calls
            start_time = time.time()
            
            for i in range(10):
                github_api_call(f"pulls/{i}", "owner", "repo")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should include rate limiting delays
            assert mock_sleep.call_count >= 10
            # Each call should have some delay, total time should reflect this
            assert total_time >= 10 * 1.0  # At least 1 second per call due to rate limiting

    def test_concurrent_request_simulation(self, mock_github_token):
        """Test performance under simulated concurrent requests."""
        import threading
        from utils.github_data_fetch import github_api_call
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('requests.get') as mock_get, \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {'X-RateLimit-Remaining': '5000'}
            mock_get.return_value = mock_response
            
            results = []
            
            def api_call_worker(call_id):
                try:
                    start = time.time()
                    github_api_call(f"pulls/{call_id}", "owner", "repo")
                    end = time.time()
                    results.append(end - start)
                except Exception as e:
                    results.append(float('inf'))
            
            # Simulate concurrent requests
            threads = []
            for i in range(10):
                thread = threading.Thread(target=api_call_worker, args=(i,))
                threads.append(thread)
            
            start_time = time.time()
            for thread in threads:
                thread.start()
            
            for thread in threads:
                thread.join()
            
            end_time = time.time()
            
            # All requests should complete reasonably quickly
            assert len(results) == 10
            assert all(result < 5.0 for result in results if result != float('inf'))
            assert end_time - start_time < 30.0  # Total time under 30 seconds


@pytest.mark.performance
@pytest.mark.slow
class TestSummarisationPerformance:
    """Test summarisation performance."""

    def test_message_extraction_performance(self, large_pr_dataset):
        """Test performance of message extraction with large datasets."""
        # Create large commit dataset
        large_commit_data = pd.DataFrame([
            {
                'PR Number': i % 100 + 1,  # 100 different PRs
                'PR Title': f'PR #{i % 100 + 1} - Feature Implementation',
                'Commit SHA': f'commit{i:06d}',
                'Commit Message': f'Implement feature {i} with comprehensive testing and documentation'
            }
            for i in range(5000)  # 5000 commits
        ])
        
        # Measure performance
        start_time = time.time()
        
        messages = extract_messages_from_commits(large_commit_data)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertions
        assert processing_time < 10.0, f"Message extraction took too long: {processing_time}s"
        assert isinstance(messages, str)
        assert len(messages) > 0
        assert "PR #1" in messages
        assert "PR #100" in messages

    @pytest.mark.benchmark
    def test_message_extraction_benchmark(self, benchmark):
        """Benchmark message extraction performance."""
        # Generate test data
        commit_data = pd.DataFrame([
            {
                'PR Number': i % 10 + 1,
                'PR Title': f'PR #{i % 10 + 1}',
                'Commit Message': f'Commit message {i}'
            }
            for i in range(1000)
        ])
        
        # Benchmark the function
        result = benchmark(extract_messages_from_commits, commit_data)
        
        # Verify results
        assert isinstance(result, str)
        assert len(result) > 0

    def test_openai_api_performance(self, mock_openai_key):
        """Test OpenAI API call performance."""
        with patch('utils.summarisation.get_secure_openai_key', return_value=mock_openai_key), \
             patch('openai.OpenAI') as mock_openai_client, \
             patch('streamlit.error'):
            
            # Simulate realistic response time
            def slow_api_call(*args, **kwargs):
                time.sleep(0.1)  # Simulate network delay
                mock_response = Mock()
                mock_choice = Mock()
                mock_message = Mock()
                mock_message.content = "# Changelog\n\n## Fixed\n- Performance improvements"
                mock_choice.message = mock_message
                mock_response.choices = [mock_choice]
                return mock_response
            
            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.side_effect = slow_api_call
            mock_openai_client.return_value = mock_client_instance
            
            # Generate large input
            large_input = "\n\n".join([
                f"PR #{i}: Feature {i}\n- Commit {i}.1\n- Commit {i}.2"
                for i in range(100)
            ])
            
            # Measure performance
            start_time = time.time()
            
            result = gpt_inference_changelog(
                large_input, date(2024, 1, 1), date(2024, 1, 31),
                "owner", "repo", "description", ["main"]
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Should complete within reasonable time
            assert processing_time < 5.0, f"OpenAI API call took too long: {processing_time}s"
            assert result is not None


@pytest.mark.performance
class TestSecurityPerformance:
    """Test security function performance."""

    @pytest.mark.benchmark
    def test_commit_sanitization_benchmark(self, benchmark, malicious_input_samples):
        """Benchmark commit message sanitization."""
        # Use malicious samples for testing
        test_messages = []
        for category, samples in malicious_input_samples.items():
            test_messages.extend(samples)
        
        # Create a large test string
        large_message = " ".join(test_messages * 100)
        
        # Benchmark the function
        result = benchmark(sanitize_commit_message, large_message)
        
        # Verify sanitization worked
        assert isinstance(result, str)
        assert len(result) > 0

    def test_api_sanitization_performance(self, malicious_input_samples):
        """Test API response sanitization performance."""
        # Create large nested data structure
        large_api_data = {
            'items': [
                {
                    'title': sample,
                    'message': sample,
                    'number': i,
                    'nested': {
                        'description': sample,
                        'commit': {'message': sample}
                    }
                }
                for i, sample in enumerate(malicious_input_samples['xss_attempts'] * 250)
            ]
        }
        
        # Measure performance
        start_time = time.time()
        
        result = sanitize_api_response(large_api_data)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertions
        assert processing_time < 5.0, f"API sanitization took too long: {processing_time}s"
        assert isinstance(result, dict)
        assert 'items' in result

    def test_bulk_url_validation_performance(self):
        """Test URL validation performance with bulk operations."""
        from utils.security import validate_repository_url
        
        # Generate test URLs
        test_urls = [
            f"https://github.com/user{i}/repo{i}"
            for i in range(1000)
        ]
        
        # Measure performance
        start_time = time.time()
        
        results = []
        for url in test_urls:
            try:
                owner, repo = validate_repository_url(url)
                results.append((owner, repo))
            except ValueError:
                results.append((None, None))
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertions
        assert processing_time < 2.0, f"URL validation took too long: {processing_time}s"
        assert len(results) == 1000
        assert all(result[0] and result[1] for result in results)


@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage and efficiency."""

    def test_large_dataset_memory_efficiency(self):
        """Test memory efficiency with large datasets."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large dataset
        large_data = pd.DataFrame([
            {
                'PR Number': i,
                'PR Title': f'Large PR {i}',
                'Commit Message': f'Large commit message {i} ' * 100  # Large text
            }
            for i in range(10000)
        ])
        
        # Process data
        messages = extract_messages_from_commits(large_data)
        
        # Get peak memory usage
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Clean up
        del large_data
        del messages
        gc.collect()
        
        # Memory usage should be reasonable
        assert memory_increase < 500, f"Memory usage too high: {memory_increase}MB"

    def test_memory_cleanup_after_processing(self):
        """Test that memory is properly cleaned up after processing."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process multiple datasets
        for batch in range(5):
            data = pd.DataFrame([
                {
                    'PR Number': i + batch * 1000,
                    'PR Title': f'Batch {batch} PR {i}',
                    'Commit Message': f'Batch {batch} commit {i}'
                }
                for i in range(2000)
            ])
            
            messages = extract_messages_from_commits(data)
            
            # Clean up explicitly
            del data
            del messages
            gc.collect()
        
        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Should not have significant memory leak
        assert memory_increase < 100, f"Possible memory leak: {memory_increase}MB increase"


@pytest.mark.performance
@pytest.mark.slow
class TestScalabilityLimits:
    """Test scalability limits and boundaries."""

    def test_maximum_pr_count_handling(self, mock_github_token):
        """Test handling of maximum PR counts."""
        # Test with very large PR count
        max_prs = 10000
        
        large_pr_data = [
            {
                'number': i,
                'title': f'PR #{i}',
                'merged_at': f'2024-01-{(i % 28) + 1:02d}T10:30:00Z',
                'head': {'repo': {'description': 'Scalability test'}}
            }
            for i in range(1, max_prs + 1)
        ]
        
        with patch('utils.github_data_fetch.get_secure_github_token', return_value=mock_github_token), \
             patch('utils.github_data_fetch.github_api_call') as mock_api_call, \
             patch('utils.github_data_fetch.sanitize_api_response', return_value=large_pr_data), \
             patch('streamlit.error'), \
             patch('streamlit.stop'):
            
            mock_response = Mock()
            mock_response.json.return_value = large_pr_data
            mock_api_call.return_value = mock_response
            
            start_time = time.time()
            
            prs_df, _ = fetch_prs_merged_between_dates(
                "owner", "repo", date(2024, 1, 1), date(2024, 1, 31)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Should handle large datasets within reasonable time
            assert processing_time < 30.0, f"Large dataset processing took too long: {processing_time}s"
            assert len(prs_df) == max_prs

    def test_maximum_commit_message_length(self):
        """Test handling of very long commit messages."""
        # Create commit with extremely long message
        very_long_message = "Very long commit message " * 10000  # ~250KB message
        
        start_time = time.time()
        result = sanitize_commit_message(very_long_message)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should handle long messages quickly
        assert processing_time < 1.0, f"Long message processing took too long: {processing_time}s"
        assert isinstance(result, str)

    def test_deeply_nested_api_response(self):
        """Test handling of deeply nested API responses."""
        # Create deeply nested structure
        nested_data = {'level': 0}
        current = nested_data
        
        for i in range(100):  # 100 levels deep
            current['nested'] = {
                'title': f'Level {i}',
                'message': f'Message at level {i}',
                'level': i + 1
            }
            current = current['nested']
        
        start_time = time.time()
        result = sanitize_api_response(nested_data)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should handle deep nesting reasonably
        assert processing_time < 2.0, f"Deep nesting processing took too long: {processing_time}s"
        assert isinstance(result, dict)