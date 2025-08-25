import streamlit as st
import re
import pandas as pd
import logging
import time
from datetime import datetime
from typing import Tuple, Optional, List

from utils.github_data_fetch import (
    fetch_prs_merged_between_dates, 
    fetch_commits_from_prs,
)
from utils.summarisation import (
    gpt_inference_changelog, 
    extract_messages_from_commits,
)
from utils.security import validate_repository_url, show_privacy_notice
from utils.performance import (
    get_performance_monitor, 
    show_cache_statistics,
    clear_all_caches,
    benchmark_current_setup
)
from config.exceptions import GitHubAPIError, OpenAIAPIError, ValidationError
from config.settings import get_secure_github_token, request_github_token_from_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.title('🚀 Changelog Auto-Generator (Optimized)')
st.markdown("This app generates a CloudFix changelog with advanced performance optimizations.")

# Initialize performance monitoring
monitor = get_performance_monitor()
monitor.start_monitoring()

# Performance controls in sidebar
st.sidebar.header("⚡ Performance Controls")
if st.sidebar.button("🗑️ Clear All Caches"):
    clear_all_caches()

if st.sidebar.button("🏋️ Run Benchmark"):
    benchmark_current_setup()

show_cache_statistics()
show_metrics = st.sidebar.checkbox("📊 Show Performance Metrics", value=False)

# Show privacy notice and get consent
if not show_privacy_notice():
    st.warning("Please review and accept the privacy notice to continue.")
    st.stop()

def validate_github_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Validate GitHub URL and extract owner/repo with security checks."""
    try:
        return validate_repository_url(url)
    except ValueError as e:
        logger.warning(f"Invalid repository URL: {e}")
        return None, None

# Input fields
repository = st.text_input(
    'Repository URL', 
    'https://github.com/trilogy-group/cloudfix-aws',
    help="💡 Large repositories may take longer to process"
)
owner, repo = validate_github_url(repository)
if not owner or not repo:
    st.error('Invalid repository URL')
    st.stop()

# Validate GitHub token early - outside of any cached functions
github_token = get_secure_github_token()
if not github_token:
    st.warning("GitHub token not found in secrets or environment variables.")
    github_token = request_github_token_from_user()
    if not github_token:
        st.error("GitHub token is required to fetch repository data.")
        st.info("Please add your GitHub token to Streamlit secrets or environment variables for automatic authentication.")
        st.stop()

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        'Start Date',
        help="💡 Shorter date ranges process faster"
    )
with col2:
    end_date = st.date_input(
        'End Date',
        help="💡 Avoid very large date ranges for better performance"
    )

# Show performance estimate
if start_date and end_date:
    date_range_days = (end_date - start_date).days
    if date_range_days > 365:
        st.warning(f"⚠️ Large date range ({date_range_days} days) may impact performance")
    elif date_range_days > 90:
        st.info(f"ℹ️ Medium date range ({date_range_days} days) - expect moderate processing time")
    else:
        st.success(f"✅ Small date range ({date_range_days} days) - optimal for performance")

available_branches = ['production', 'staging', 'qa', 'main', 'master', 'develop']
selected_branches = st.multiselect(
    'Select branches to scan (default: production)',
    available_branches,
    default=['production'],
    help="💡 Selecting fewer branches improves performance"
)

# Performance settings
with st.expander("⚡ Advanced Performance Settings", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        max_pages = st.slider(
            "Max pages to fetch per branch",
            min_value=1,
            max_value=20,
            value=10,
            help="Higher values fetch more PRs but take longer"
        )
    
    with col2:
        concurrent_workers = st.slider(
            "Concurrent API workers",
            min_value=1,
            max_value=10,
            value=5,
            help="Higher values are faster but use more resources"
        )
        
    use_cache = st.checkbox(
        "Use intelligent caching",
        value=True,
        help="Dramatically improves performance for repeated requests"
    )

if not selected_branches:
    st.error('Please select at least one branch')
    st.stop()

st.markdown("---")

# Enhanced summary with performance info
info_cols = st.columns(4)
with info_cols[0]:
    st.metric("Repository", f"{owner}/{repo}")
with info_cols[1]:
    date_range_days = (end_date - start_date).days if start_date and end_date else 0
    st.metric("Date Range", f"{date_range_days} days")
with info_cols[2]:
    st.metric("Branches", len(selected_branches))
with info_cols[3]:
    cache_status = "✅ Enabled" if use_cache else "❌ Disabled"
    st.metric("Caching", cache_status)

# Performance estimate
estimated_time = len(selected_branches) * max(1, date_range_days // 30) * 5
if estimated_time > 60:
    st.warning(f"⏱️ Estimated time: {estimated_time//60}+ minutes")
else:
    st.info(f"⏱️ Estimated time: ~{estimated_time} seconds")

if st.button('🎯 Generate Optimized Changelog'):
    try:
        # Record session start
        session_start = time.time()
        monitor.record_memory_snapshot()
        
        all_prs = []
        repo_description = None
        
        # Phase 1: Fetch PRs with progress tracking
        phase_progress = st.progress(0)
        st.text("Phase 1/3: Fetching PRs with optimization...")
        
        for i, branch in enumerate(selected_branches):
            phase_progress.progress((i + 0.5) / len(selected_branches) * 0.33)
            
            with st.spinner(f'Fetching PRs from {branch} branch...'):
                branch_prs, repo_description = fetch_prs_merged_between_dates(owner, repo, start_date, end_date, branch)
                monitor.record_api_call()
                
                if branch_prs is not None and not branch_prs.empty:
                    branch_prs['branch'] = branch
                    all_prs.append(branch_prs)
                    st.success(f"✅ Found {len(branch_prs)} PRs in {branch} branch")
                else:
                    st.warning(f"⚠️ No PRs found in {branch} branch")
        
        if not all_prs:
            st.error("Failed to fetch PRs or no PRs found")
            st.stop()
            
        # Combine and deduplicate PRs
        prs = pd.concat(all_prs, ignore_index=True)
        total_prs = len(prs)
        prs = prs.drop_duplicates(subset=['number'], keep='first')
        unique_prs = len(prs)
        
        if unique_prs < total_prs:
            st.info(f"ℹ️ Removed {total_prs - unique_prs} duplicate PRs")
        
        st.success(f"✅ Found {unique_prs} unique PRs across {len(selected_branches)} branches")
        phase_progress.progress(0.33)
        
        # Phase 2: Fetch commits with concurrent processing
        st.text("Phase 2/3: Fetching commits (concurrent processing)...")
        
        with st.spinner(f'Fetching commits from {unique_prs} PRs...'):
            commits = fetch_commits_from_prs(prs, owner, repo)
            monitor.record_memory_snapshot()
            
            if commits.empty:
                st.warning("⚠️ No commits found in the selected PRs")
            else:
                st.success(f"✅ Found {len(commits)} commits")
                
        phase_progress.progress(0.66)
        
        # Phase 3: Generate changelog with AI
        st.text("Phase 3/3: Generating changelog with AI...")
        
        with st.spinner('Processing commit messages...'):
            messages = extract_messages_from_commits(commits)
            
            if not messages.strip():
                st.error("No valid commit messages found to generate changelog")
                st.stop()
            
            st.info(f"📝 Processing {len(messages.split('PR #'))-1} PRs for changelog generation")
            
        changelog = gpt_inference_changelog(
            messages, 
            start_date, 
            end_date,
            owner, 
            repo, 
            repo_description, 
            selected_branches
        )
        
        phase_progress.progress(1.0)
        
        # Display results
        if changelog:
            total_time = time.time() - session_start
            monitor.record_operation("full_changelog_generation", total_time, True)
            
            st.markdown("## 📋 Generated Changelog")
            st.markdown(changelog)
            
            # Enhanced download options
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="📥 Download Changelog (Markdown)",
                    data=changelog,
                    file_name=f"changelog_{owner}_{repo}_{start_date}_to_{end_date}.md",
                    mime="text/markdown"
                )
            
            with col2:
                plain_text = changelog.replace("#", "").replace("*", "-")
                st.download_button(
                    label="📄 Download Changelog (Text)",
                    data=plain_text,
                    file_name=f"changelog_{owner}_{repo}_{start_date}_to_{end_date}.txt",
                    mime="text/plain"
                )
            
            # Performance summary
            st.success(f"✅ Changelog generated successfully in {total_time:.1f}s")
            
            # Enhanced data display
            with st.expander("🔍 View Detailed PR Data"):
                display_columns = ['title', 'number', 'merged_at', 'branch'] if 'branch' in prs.columns else ['title', 'number', 'merged_at']
                st.dataframe(
                    prs[display_columns].sort_values('merged_at', ascending=False),
                    use_container_width=True
                )
            
            with st.expander("💻 View Commit Details"):
                if not commits.empty:
                    st.dataframe(
                        commits[['PR Number', 'PR Title', 'Commit Message']],
                        use_container_width=True
                    )
                else:
                    st.info("No commit details available")
                    
        else:
            st.error("Failed to generate changelog")
            monitor.record_operation("full_changelog_generation", time.time() - session_start, False)
        
        phase_progress.empty()
        
        # Show performance metrics if enabled
        if show_metrics:
            with st.expander("📊 Performance Report", expanded=False):
                monitor.display_performance_metrics()
                    
    except GitHubAPIError as e:
        monitor.record_operation("github_api_error", 0, False)
        st.error(f"GitHub API Error: {str(e)}")
        if hasattr(e, 'status_code') and e.status_code == 401:
            st.info("💡 Please check your GitHub token permissions")
        elif hasattr(e, 'status_code') and e.status_code == 403:
            st.info("💡 Rate limit exceeded. Try clearing caches and wait a few minutes")
            if st.button("🗑️ Clear Caches to Reset"):
                clear_all_caches()
    
    except OpenAIAPIError as e:
        monitor.record_operation("openai_api_error", 0, False)
        st.error(f"OpenAI API Error: {str(e)}")
        st.info("💡 Please check your OpenAI API key configuration")
        st.info("🔧 Verify your API key has sufficient credits and permissions")
    
    except ValidationError as e:
        monitor.record_operation("validation_error", 0, False)
        st.error(f"Validation Error: {str(e)}")
        st.info("💡 Please check your input parameters")
        st.info("🔧 Ensure dates are valid and repository URL is correct")
    
    except Exception as e:
        monitor.record_operation("unexpected_error", 0, False)
        st.error(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error in main workflow: {e}", exc_info=True)
        st.info("💡 Please try again or contact support if the problem persists")
        
        # Debugging options
        with st.expander("🔧 Debugging Options"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear All Caches"):
                    clear_all_caches()
            with col2:
                if st.button("Run System Benchmark"):
                    benchmark_current_setup()


# Performance optimizations summary
st.markdown("---")
with st.expander("⚡ Performance Optimizations Implemented", expanded=False):
    st.markdown("""
    ### 🚀 Speed Improvements:
    - **Concurrent API Calls**: Multiple GitHub API calls run in parallel
    - **Smart Caching**: API responses cached for 30-60 minutes
    - **Pagination**: Efficiently fetches all PRs across multiple pages
    - **Early Termination**: Stops fetching when no more relevant data found
    - **Vectorized Operations**: Pandas operations optimized for large datasets
    
    ### 💾 Memory Optimizations:
    - **Streaming Processing**: Data processed in chunks to reduce memory usage
    - **Smart Filtering**: Filter data as early as possible
    - **Cache Management**: Automatic cleanup of expired cache files
    - **Memory Monitoring**: Track memory usage throughout the process
    
    ### 🛠 User Experience:
    - **Progress Tracking**: Real-time progress indicators for all phases
    - **Performance Metrics**: Optional detailed performance reporting
    - **Cache Controls**: Manual cache management options
    - **Error Recovery**: Better error handling with recovery suggestions
    - **Benchmarking**: Built-in system performance testing
    """)

if __name__ == "__main__":
    pass 