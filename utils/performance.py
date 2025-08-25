"""Performance monitoring and benchmarking utilities."""

import time
import logging
import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from functools import wraps
from datetime import datetime
import psutil
import os

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Performance monitoring class for tracking application metrics."""
    
    def __init__(self):
        self.metrics = {}
        self.start_time = None
        self.memory_usage = []
        
    def start_monitoring(self):
        """Start performance monitoring session."""
        self.start_time = time.time()
        self.metrics = {
            'session_start': datetime.now(),
            'operations': [],
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0,
            'errors': 0
        }
        
    def record_operation(self, operation: str, duration: float, success: bool = True):
        """Record an operation's performance metrics."""
        if 'operations' not in self.metrics:
            self.metrics['operations'] = []
            
        self.metrics['operations'].append({
            'operation': operation,
            'duration': duration,
            'timestamp': datetime.now(),
            'success': success
        })
        
        if not success:
            self.metrics['errors'] += 1
            
    def record_cache_event(self, hit: bool):
        """Record cache hit or miss."""
        if hit:
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
            
    def record_api_call(self):
        """Record an API call."""
        self.metrics['api_calls'] += 1
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
        
    def record_memory_snapshot(self):
        """Record current memory usage."""
        self.memory_usage.append({
            'timestamp': datetime.now(),
            'memory_mb': self.get_memory_usage()
        })
        
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.start_time:
            return {}
            
        total_duration = time.time() - self.start_time
        operations = self.metrics.get('operations', [])
        
        # Calculate operation statistics
        operation_stats = {}
        for op in operations:
            op_name = op['operation']
            if op_name not in operation_stats:
                operation_stats[op_name] = {
                    'count': 0,
                    'total_time': 0,
                    'min_time': float('inf'),
                    'max_time': 0,
                    'success_count': 0
                }
            
            stats = operation_stats[op_name]
            stats['count'] += 1
            stats['total_time'] += op['duration']
            stats['min_time'] = min(stats['min_time'], op['duration'])
            stats['max_time'] = max(stats['max_time'], op['duration'])
            if op['success']:
                stats['success_count'] += 1
        
        # Calculate averages
        for stats in operation_stats.values():
            stats['avg_time'] = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            stats['success_rate'] = stats['success_count'] / stats['count'] if stats['count'] > 0 else 0
            
        # Cache efficiency
        total_cache_ops = self.metrics['cache_hits'] + self.metrics['cache_misses']
        cache_hit_rate = self.metrics['cache_hits'] / total_cache_ops if total_cache_ops > 0 else 0
        
        return {
            'session_duration': total_duration,
            'operation_stats': operation_stats,
            'api_calls': self.metrics['api_calls'],
            'cache_hit_rate': cache_hit_rate,
            'cache_hits': self.metrics['cache_hits'],
            'cache_misses': self.metrics['cache_misses'],
            'errors': self.metrics['errors'],
            'memory_snapshots': self.memory_usage,
            'current_memory_mb': self.get_memory_usage()
        }
        
    def display_performance_metrics(self):
        """Display performance metrics in Streamlit."""
        report = self.get_performance_report()
        if not report:
            return
            
        st.subheader("🏃 Performance Metrics")
        
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Time", 
                f"{report['session_duration']:.1f}s"
            )
            
        with col2:
            st.metric(
                "API Calls", 
                report['api_calls']
            )
            
        with col3:
            st.metric(
                "Cache Hit Rate", 
                f"{report['cache_hit_rate']:.1%}"
            )
            
        with col4:
            st.metric(
                "Memory Usage", 
                f"{report['current_memory_mb']:.1f} MB"
            )
        
        # Operation breakdown
        if report['operation_stats']:
            st.subheader("Operation Performance")
            
            # Create DataFrame for operation stats
            op_data = []
            for op_name, stats in report['operation_stats'].items():
                op_data.append({
                    'Operation': op_name,
                    'Count': stats['count'],
                    'Avg Time (s)': f"{stats['avg_time']:.2f}",
                    'Min Time (s)': f"{stats['min_time']:.2f}",
                    'Max Time (s)': f"{stats['max_time']:.2f}",
                    'Success Rate': f"{stats['success_rate']:.1%}"
                })
            
            df = pd.DataFrame(op_data)
            st.dataframe(df, use_container_width=True)
        
        # Performance recommendations
        self._show_performance_recommendations(report)
        
    def _show_performance_recommendations(self, report: Dict[str, Any]):
        """Show performance improvement recommendations."""
        recommendations = []
        
        # Check cache performance
        if report['cache_hit_rate'] < 0.5 and report['cache_hits'] + report['cache_misses'] > 10:
            recommendations.append(
                "🔄 Low cache hit rate detected. Consider increasing cache TTL or reviewing cache keys."
            )
        
        # Check memory usage
        if report['current_memory_mb'] > 500:
            recommendations.append(
                "🧠 High memory usage detected. Consider processing data in smaller chunks."
            )
        
        # Check API call efficiency
        if report['api_calls'] > 100:
            recommendations.append(
                "🚀 High API call count. Consider implementing better pagination or filtering."
            )
        
        # Check for slow operations
        for op_name, stats in report.get('operation_stats', {}).items():
            if stats['avg_time'] > 10:
                recommendations.append(
                    f"⏱️ Slow operation detected: {op_name} (avg: {stats['avg_time']:.1f}s)"
                )
        
        if recommendations:
            st.subheader("💡 Performance Recommendations")
            for rec in recommendations:
                st.info(rec)

# Global performance monitor instance
_performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _performance_monitor

def performance_benchmark(func):
    """Decorator for benchmarking function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        monitor = get_performance_monitor()
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            monitor.record_operation(func.__name__, duration, True)
            logger.info(f"Performance: {func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            monitor.record_operation(func.__name__, duration, False)
            logger.error(f"Performance: {func.__name__} failed after {duration:.2f}s: {e}")
            raise
    return wrapper

def show_cache_statistics():
    """Display cache statistics in the UI."""
    st.sidebar.subheader("📊 Cache Statistics")
    monitor = get_performance_monitor()
    
    total_ops = monitor.metrics['cache_hits'] + monitor.metrics['cache_misses']
    if total_ops > 0:
        hit_rate = monitor.metrics['cache_hits'] / total_ops
        st.sidebar.metric("Cache Hit Rate", f"{hit_rate:.1%}")
        st.sidebar.metric("Cache Hits", monitor.metrics['cache_hits'])
        st.sidebar.metric("Cache Misses", monitor.metrics['cache_misses'])
    else:
        st.sidebar.info("No cache operations yet")

def clear_all_caches():
    """Clear all application caches."""
    try:
        # Clear Streamlit cache
        st.cache_data.clear()
        
        # Clear custom caches
        import shutil
        cache_dirs = ["/tmp/changelog_cache", "/tmp/openai_cache"]
        
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                
        st.success("✅ All caches cleared successfully!")
        logger.info("All caches cleared")
        
    except Exception as e:
        st.error(f"Error clearing caches: {e}")
        logger.error(f"Cache clear error: {e}")

def benchmark_current_setup():
    """Run a quick benchmark of the current setup."""
    st.subheader("🏋️ Performance Benchmark")
    
    benchmark_results = {}
    
    # Test GitHub API response time
    with st.spinner("Testing GitHub API response..."):
        start_time = time.time()
        try:
            import requests
            response = requests.get("https://api.github.com/rate_limit", timeout=5)
            api_time = time.time() - start_time
            benchmark_results['github_api'] = {
                'time': api_time,
                'status': 'success' if response.status_code == 200 else 'error'
            }
        except Exception as e:
            benchmark_results['github_api'] = {
                'time': time.time() - start_time,
                'status': 'error',
                'error': str(e)
            }
    
    # Test memory allocation
    start_time = time.time()
    test_data = list(range(100000))  # Allocate some memory
    memory_time = time.time() - start_time
    del test_data  # Free memory
    benchmark_results['memory_allocation'] = {
        'time': memory_time,
        'status': 'success'
    }
    
    # Display results
    col1, col2 = st.columns(2)
    
    with col1:
        github_result = benchmark_results['github_api']
        st.metric(
            "GitHub API Response", 
            f"{github_result['time']:.2f}s",
            delta="Fast" if github_result['time'] < 1.0 else "Slow"
        )
    
    with col2:
        memory_result = benchmark_results['memory_allocation']
        st.metric(
            "Memory Allocation", 
            f"{memory_result['time']:.2f}s",
            delta="Fast" if memory_result['time'] < 0.1 else "Slow"
        )
    
    # Overall assessment
    if benchmark_results['github_api']['time'] < 1.0 and memory_result['time'] < 0.1:
        st.success("🚀 System performance looks good!")
    else:
        st.warning("⚠️ System performance could be improved")
    
    return benchmark_results