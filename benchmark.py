#!/usr/bin/env python3
"""
Performance Benchmark Suite for Changelog Generator

This script runs comprehensive performance tests on the changelog generator
to measure improvements and identify bottlenecks.
"""

import time
import os
import sys
import json
import statistics
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
import pandas as pd
import requests
import psutil

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.github_data_fetch import (
    fetch_prs_merged_between_dates, 
    fetch_commits_from_prs,
    get_cached_data,
    cache_data
)
from utils.summarisation import (
    extract_messages_from_commits,
    gpt_inference_changelog
)
from config.settings import AppConfig

class PerformanceBenchmark:
    """Comprehensive performance benchmark suite."""
    
    def __init__(self):
        self.results = {}
        self.test_start_time = None
        self.config = AppConfig()
        
    def start_benchmark(self):
        """Initialize benchmark session."""
        self.test_start_time = time.time()
        self.results = {
            'benchmark_start': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'tests': {}
        }
        print("🏋️  Starting Performance Benchmark Suite")
        print("=" * 50)
        
    def _get_system_info(self) -> Dict[str, Any]:
        """Collect system information."""
        return {
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'python_version': sys.version,
            'platform': sys.platform,
        }
    
    def benchmark_github_api_response(self) -> Dict[str, float]:
        """Benchmark GitHub API response times."""
        print("\n📡 Testing GitHub API Response Times...")
        
        test_urls = [
            "https://api.github.com/rate_limit",
            "https://api.github.com/user",
            "https://api.github.com/repos/octocat/Hello-World"
        ]
        
        response_times = []
        
        for url in test_urls:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=10)
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times.append(response_time)
                
                status = "✅" if response.status_code == 200 else "❌"
                print(f"  {status} {url.split('/')[-1]}: {response_time:.3f}s")
                
            except Exception as e:
                print(f"  ❌ {url.split('/')[-1]}: Failed ({str(e)})")
                response_times.append(10.0)  # Penalty for failure
        
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        result = {
            'avg_response_time': avg_response_time,
            'min_response_time': min_response_time,
            'max_response_time': max_response_time,
            'total_tests': len(test_urls),
            'success_rate': sum(1 for t in response_times if t < 5.0) / len(test_urls)
        }
        
        self.results['tests']['github_api'] = result
        
        print(f"  📊 Average response time: {avg_response_time:.3f}s")
        print(f"  📊 Success rate: {result['success_rate']:.1%}")
        
        return result
    
    def benchmark_data_processing(self) -> Dict[str, float]:
        """Benchmark data processing operations."""
        print("\n🔄 Testing Data Processing Performance...")
        
        # Generate test data
        test_sizes = [100, 500, 1000, 2000]
        processing_times = []
        
        for size in test_sizes:
            print(f"  Testing with {size} records...")
            
            # Create test DataFrame
            test_data = pd.DataFrame({
                'PR Number': range(1, size + 1),
                'PR Title': [f'Test PR {i}' for i in range(1, size + 1)],
                'Commit Message': [f'Test commit message {i}' for i in range(1, size + 1)]
            })
            
            # Benchmark commit message extraction
            start_time = time.time()
            messages = extract_messages_from_commits(test_data)
            processing_time = time.time() - start_time
            
            processing_times.append(processing_time)
            
            throughput = size / processing_time if processing_time > 0 else float('inf')
            print(f"    ⚡ {size} records: {processing_time:.3f}s ({throughput:.0f} records/sec)")
        
        avg_processing_time = statistics.mean(processing_times)
        
        result = {
            'avg_processing_time': avg_processing_time,
            'test_sizes': test_sizes,
            'processing_times': processing_times,
            'max_throughput': max([size/time for size, time in zip(test_sizes, processing_times)])
        }
        
        self.results['tests']['data_processing'] = result
        
        print(f"  📊 Average processing time: {avg_processing_time:.3f}s")
        print(f"  📊 Max throughput: {result['max_throughput']:.0f} records/sec")
        
        return result
    
    def benchmark_memory_usage(self) -> Dict[str, float]:
        """Benchmark memory usage patterns."""
        print("\n🧠 Testing Memory Usage...")
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test memory allocation patterns
        memory_snapshots = [initial_memory]
        
        # Simulate data loading
        test_data_sizes = [1000, 5000, 10000]
        
        for size in test_data_sizes:
            # Create large test dataset
            large_data = pd.DataFrame({
                'column_' + str(i): range(size) for i in range(10)
            })
            
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_snapshots.append(current_memory)
            print(f"  📈 After loading {size} records: {current_memory:.1f} MB")
            
            # Clean up
            del large_data
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_snapshots.append(final_memory)
        
        max_memory = max(memory_snapshots)
        memory_growth = max_memory - initial_memory
        
        result = {
            'initial_memory_mb': initial_memory,
            'max_memory_mb': max_memory,
            'final_memory_mb': final_memory,
            'memory_growth_mb': memory_growth,
            'memory_snapshots': memory_snapshots
        }
        
        self.results['tests']['memory_usage'] = result
        
        print(f"  📊 Initial memory: {initial_memory:.1f} MB")
        print(f"  📊 Peak memory: {max_memory:.1f} MB")
        print(f"  📊 Memory growth: {memory_growth:.1f} MB")
        
        return result
    
    def benchmark_cache_performance(self) -> Dict[str, float]:
        """Benchmark caching system performance."""
        print("\n🗄️  Testing Cache Performance...")
        
        # Test cache write performance
        test_data = {'test_key': 'test_value', 'large_data': list(range(1000))}
        cache_key = 'benchmark_test_key'
        
        # Write performance
        write_times = []
        for i in range(10):
            start_time = time.time()
            cache_data(f"{cache_key}_{i}", test_data)
            write_time = time.time() - start_time
            write_times.append(write_time)
        
        avg_write_time = statistics.mean(write_times)
        print(f"  ✍️  Average cache write time: {avg_write_time:.4f}s")
        
        # Read performance
        read_times = []
        cache_hits = 0
        
        for i in range(10):
            start_time = time.time()
            cached_data = get_cached_data(f"{cache_key}_{i}")
            read_time = time.time() - start_time
            read_times.append(read_time)
            
            if cached_data is not None:
                cache_hits += 1
        
        avg_read_time = statistics.mean(read_times)
        cache_hit_rate = cache_hits / 10
        
        print(f"  📖 Average cache read time: {avg_read_time:.4f}s")
        print(f"  📊 Cache hit rate: {cache_hit_rate:.1%}")
        
        result = {
            'avg_write_time': avg_write_time,
            'avg_read_time': avg_read_time,
            'cache_hit_rate': cache_hit_rate,
            'write_times': write_times,
            'read_times': read_times
        }
        
        self.results['tests']['cache_performance'] = result
        return result
    
    def benchmark_concurrent_processing(self) -> Dict[str, float]:
        """Benchmark concurrent processing capabilities."""
        print("\n🚀 Testing Concurrent Processing...")
        
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        def cpu_intensive_task(n):
            """CPU-intensive task for testing."""
            result = 0
            for i in range(n):
                result += i ** 0.5
            return result
        
        task_size = 100000
        num_tasks = 10
        
        # Sequential processing
        start_time = time.time()
        sequential_results = [cpu_intensive_task(task_size) for _ in range(num_tasks)]
        sequential_time = time.time() - start_time
        
        print(f"  🐌 Sequential processing: {sequential_time:.3f}s")
        
        # Concurrent processing
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            concurrent_results = list(executor.map(cpu_intensive_task, [task_size] * num_tasks))
        concurrent_time = time.time() - start_time
        
        print(f"  🚀 Concurrent processing: {concurrent_time:.3f}s")
        
        speedup = sequential_time / concurrent_time if concurrent_time > 0 else 0
        efficiency = speedup / min(5, num_tasks)  # 5 workers
        
        result = {
            'sequential_time': sequential_time,
            'concurrent_time': concurrent_time,
            'speedup': speedup,
            'efficiency': efficiency,
            'num_tasks': num_tasks,
            'num_workers': 5
        }
        
        self.results['tests']['concurrent_processing'] = result
        
        print(f"  📊 Speedup: {speedup:.2f}x")
        print(f"  📊 Efficiency: {efficiency:.1%}")
        
        return result
    
    def benchmark_end_to_end(self, test_repo: str = "octocat/Hello-World") -> Dict[str, float]:
        """Benchmark end-to-end performance with a test repository."""
        print(f"\n🎯 End-to-End Test with {test_repo}...")
        
        # Use a small date range for testing
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        try:
            # Parse repo
            owner, repo = test_repo.split('/')
            
            # Phase 1: Fetch PRs
            print("  📡 Fetching PRs...")
            pr_start_time = time.time()
            prs, repo_description = fetch_prs_merged_between_dates(
                owner, repo, start_date, end_date, 'main'
            )
            pr_fetch_time = time.time() - pr_start_time
            
            pr_count = len(prs) if prs is not None and not prs.empty else 0
            print(f"    ✅ Found {pr_count} PRs in {pr_fetch_time:.2f}s")
            
            if pr_count == 0:
                result = {
                    'pr_fetch_time': pr_fetch_time,
                    'pr_count': 0,
                    'commit_fetch_time': 0,
                    'commit_count': 0,
                    'total_time': pr_fetch_time,
                    'success': False,
                    'error': 'No PRs found in date range'
                }
            else:
                # Phase 2: Fetch commits (limited for testing)
                print("  💻 Fetching commits...")
                limited_prs = prs.head(5)  # Limit to first 5 PRs for testing
                
                commit_start_time = time.time()
                commits = fetch_commits_from_prs(limited_prs, owner, repo)
                commit_fetch_time = time.time() - commit_start_time
                
                commit_count = len(commits) if commits is not None and not commits.empty else 0
                print(f"    ✅ Found {commit_count} commits in {commit_fetch_time:.2f}s")
                
                total_time = pr_fetch_time + commit_fetch_time
                
                result = {
                    'pr_fetch_time': pr_fetch_time,
                    'pr_count': pr_count,
                    'commit_fetch_time': commit_fetch_time,
                    'commit_count': commit_count,
                    'total_time': total_time,
                    'success': True,
                    'throughput_prs_per_sec': pr_count / pr_fetch_time if pr_fetch_time > 0 else 0,
                    'throughput_commits_per_sec': commit_count / commit_fetch_time if commit_fetch_time > 0 else 0
                }
        
        except Exception as e:
            print(f"    ❌ End-to-end test failed: {str(e)}")
            result = {
                'success': False,
                'error': str(e),
                'total_time': 0
            }
        
        self.results['tests']['end_to_end'] = result
        
        if result.get('success', False):
            print(f"  📊 Total time: {result['total_time']:.2f}s")
            print(f"  📊 PR throughput: {result['throughput_prs_per_sec']:.1f} PRs/sec")
            print(f"  📊 Commit throughput: {result['throughput_commits_per_sec']:.1f} commits/sec")
        
        return result
    
    def generate_performance_grade(self) -> str:
        """Generate overall performance grade based on benchmark results."""
        scores = []
        
        # GitHub API performance (target: < 1s average)
        if 'github_api' in self.results['tests']:
            api_time = self.results['tests']['github_api']['avg_response_time']
            api_score = max(0, min(100, 100 - (api_time - 0.5) * 50))
            scores.append(api_score)
        
        # Cache performance (target: > 90% hit rate)
        if 'cache_performance' in self.results['tests']:
            cache_hit_rate = self.results['tests']['cache_performance']['cache_hit_rate']
            cache_score = cache_hit_rate * 100
            scores.append(cache_score)
        
        # Memory efficiency (target: < 500MB growth)
        if 'memory_usage' in self.results['tests']:
            memory_growth = self.results['tests']['memory_usage']['memory_growth_mb']
            memory_score = max(0, min(100, 100 - (memory_growth - 200) / 5))
            scores.append(memory_score)
        
        # Concurrent processing efficiency (target: > 50% efficiency)
        if 'concurrent_processing' in self.results['tests']:
            efficiency = self.results['tests']['concurrent_processing']['efficiency']
            concurrent_score = efficiency * 100
            scores.append(concurrent_score)
        
        if not scores:
            return "No data available"
        
        overall_score = statistics.mean(scores)
        
        if overall_score >= 90:
            return "A+ (Excellent)"
        elif overall_score >= 80:
            return "A (Very Good)"
        elif overall_score >= 70:
            return "B (Good)"
        elif overall_score >= 60:
            return "C (Fair)"
        elif overall_score >= 50:
            return "D (Poor)"
        else:
            return "F (Needs Improvement)"
    
    def run_full_benchmark(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        self.start_benchmark()
        
        try:
            # Run all benchmark tests
            self.benchmark_github_api_response()
            self.benchmark_data_processing()
            self.benchmark_memory_usage()
            self.benchmark_cache_performance()
            self.benchmark_concurrent_processing()
            self.benchmark_end_to_end()
            
            # Calculate final results
            total_time = time.time() - self.test_start_time
            performance_grade = self.generate_performance_grade()
            
            self.results.update({
                'benchmark_end': datetime.now().isoformat(),
                'total_benchmark_time': total_time,
                'performance_grade': performance_grade
            })
            
            self._print_summary()
            
            return self.results
            
        except Exception as e:
            print(f"❌ Benchmark failed: {str(e)}")
            self.results['error'] = str(e)
            return self.results
    
    def _print_summary(self):
        """Print benchmark summary."""
        print("\n" + "=" * 50)
        print("📊 PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 50)
        
        print(f"🎯 Overall Grade: {self.results['performance_grade']}")
        print(f"⏱️  Total Time: {self.results['total_benchmark_time']:.1f}s")
        print(f"💻 System: {self.results['system_info']['cpu_count']} CPU cores, {self.results['system_info']['memory_total_gb']:.1f}GB RAM")
        
        print("\n📈 Test Results:")
        
        for test_name, test_results in self.results['tests'].items():
            print(f"  {test_name.replace('_', ' ').title()}:")
            
            if test_name == 'github_api':
                print(f"    • Average response: {test_results['avg_response_time']:.3f}s")
                print(f"    • Success rate: {test_results['success_rate']:.1%}")
                
            elif test_name == 'data_processing':
                print(f"    • Max throughput: {test_results['max_throughput']:.0f} records/sec")
                
            elif test_name == 'memory_usage':
                print(f"    • Peak memory: {test_results['max_memory_mb']:.1f} MB")
                print(f"    • Memory growth: {test_results['memory_growth_mb']:.1f} MB")
                
            elif test_name == 'cache_performance':
                print(f"    • Hit rate: {test_results['cache_hit_rate']:.1%}")
                print(f"    • Avg read time: {test_results['avg_read_time']:.4f}s")
                
            elif test_name == 'concurrent_processing':
                print(f"    • Speedup: {test_results['speedup']:.2f}x")
                print(f"    • Efficiency: {test_results['efficiency']:.1%}")
                
            elif test_name == 'end_to_end':
                if test_results.get('success', False):
                    print(f"    • Total time: {test_results['total_time']:.2f}s")
                    print(f"    • PR throughput: {test_results['throughput_prs_per_sec']:.1f}/sec")
                else:
                    print(f"    • ❌ Failed: {test_results.get('error', 'Unknown error')}")
        
        print("\n🎉 Benchmark completed successfully!")
    
    def save_results(self, filename: str = None):
        """Save benchmark results to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"📄 Results saved to {filename}")
        except Exception as e:
            print(f"❌ Failed to save results: {str(e)}")

def main():
    """Run the benchmark suite."""
    print("🚀 Changelog Generator Performance Benchmark")
    print("This will test various aspects of the application performance.")
    print()
    
    # Check if we have the required environment
    config = AppConfig()
    if not config.github_token:
        print("⚠️  Warning: No GitHub token found. Some tests may fail.")
    
    benchmark = PerformanceBenchmark()
    results = benchmark.run_full_benchmark()
    
    # Save results
    benchmark.save_results()
    
    return results

if __name__ == "__main__":
    main()