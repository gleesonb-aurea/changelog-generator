import requests
import pandas as pd
import time
import logging
import asyncio
import aiohttp
import hashlib
import pickle
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any
from datetime import date, datetime, timedelta
import streamlit as st
from functools import wraps

from config.settings import AppConfig, get_secure_github_token
from config.exceptions import GitHubAPIError, ValidationError
from utils.security import sanitize_api_response, filter_sensitive_logs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance monitoring decorator
def performance_timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"Performance: {func.__name__} took {end_time - start_time:.2f}s")
        return result
    return wrapper

# Cache configuration
CACHE_DIR = "/tmp/changelog_cache"
CACHE_TTL = 3600  # 1 hour

def ensure_cache_dir():
    """Ensure cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(owner: str, repo: str, start_date: date, end_date: date, branch: str) -> str:
    """Generate cache key for API responses."""
    key_data = f"{owner}/{repo}/{branch}/{start_date}/{end_date}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_cached_data(cache_key: str) -> Optional[Any]:
    """Retrieve cached data if valid."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    
    try:
        if os.path.exists(cache_file):
            # Check if cache is still valid
            cache_time = os.path.getmtime(cache_file)
            if time.time() - cache_time < CACHE_TTL:
                with open(cache_file, 'rb') as f:
                    logger.info(f"Cache hit: {cache_key}")
                    return pickle.load(f)
            else:
                # Remove expired cache
                os.remove(cache_file)
                logger.info(f"Cache expired: {cache_key}")
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    
    return None

def cache_data(cache_key: str, data: Any) -> None:
    """Cache data to disk."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"Data cached: {cache_key}")
    except Exception as e:
        logger.warning(f"Cache write error: {e}")

@performance_timer
def github_api_call(
    url_suffix: str, 
    owner: str, 
    repo: str, 
    params: Dict[str, Any] = None,
    use_rate_limit: bool = True
) -> requests.Response:
    """Make GitHub API call with proper error handling and security."""
    if params is None:
        params = {}
    
    config = AppConfig()
    token = get_secure_github_token()
    
    if not token:
        # This should not happen if token validation is done at UI level
        raise GitHubAPIError("GitHub token is not available")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f'{config.github.api_base_url}/repos/{owner}/{repo}/{url_suffix}'
    
    # Log request without sensitive data
    log_message = f"GitHub API request: {url_suffix} for {owner}/{repo}"
    logger.info(filter_sensitive_logs(log_message))
    
    try:
        # Add rate limiting only when needed
        if use_rate_limit:
            time.sleep(config.github.rate_limit_delay)
        
        response = requests.get(
            url, 
            params=params, 
            headers=headers, 
            timeout=config.github.timeout
        )
        
        # Handle rate limiting
        if response.status_code == 403:
            reset_time = response.headers.get('X-RateLimit-Reset')
            remaining = response.headers.get('X-RateLimit-Remaining', '0')
            
            if int(remaining) == 0:
                st.error(f"GitHub API rate limit exceeded. Resets at {reset_time}")
                raise GitHubAPIError("Rate limit exceeded", 403)
        
        # Check remaining requests
        remaining = response.headers.get('X-RateLimit-Remaining', '0')
        if int(remaining) < 10:
            st.warning(f"GitHub API rate limit low: {remaining} requests remaining")
        
        # Handle other HTTP errors
        if response.status_code == 404:
            raise GitHubAPIError(f"Repository {owner}/{repo} not found or not accessible", 404)
        elif response.status_code == 401:
            raise GitHubAPIError("GitHub token is invalid or expired", 401)
        elif response.status_code >= 400:
            raise GitHubAPIError(f"GitHub API error: {response.status_code}", response.status_code)
        
        logger.info(f"GitHub API response: {response.status_code}")
        return response
        
    except requests.exceptions.Timeout:
        raise GitHubAPIError("GitHub API request timeout")
    except requests.exceptions.ConnectionError:
        raise GitHubAPIError("Failed to connect to GitHub API")
    except requests.exceptions.RequestException as e:
        raise GitHubAPIError(f"GitHub API request failed: {str(e)}")

@performance_timer
@st.cache_data(ttl=3600)
def fetch_commits_from_prs_optimized(
    prs: pd.DataFrame, 
    owner: str, 
    repo: str,
    max_workers: int = 5
) -> pd.DataFrame:
    """Optimized version with concurrent processing and caching."""
    if prs.empty:
        return pd.DataFrame()
    
    all_commits = []
    pr_numbers = prs['number'].tolist()
    
    # Use ThreadPoolExecutor for concurrent API calls
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_pr = {
            executor.submit(_fetch_single_pr_commits_optimized, pr_num, owner, repo): pr_num 
            for pr_num in pr_numbers
        }
        
        # Collect results with progress tracking
        progress_bar = st.progress(0)
        completed = 0
        
        for future in as_completed(future_to_pr):
            pr_number = future_to_pr[future]
            completed += 1
            progress_bar.progress(completed / len(pr_numbers))
            
            try:
                pr_commits = future.result(timeout=30)
                if pr_commits:
                    # Get PR data for this PR number
                    pr_data = prs[prs['number'] == pr_number].iloc[0]
                    pr_commits_records = _transform_commits_to_records(pr_commits, pr_data)
                    all_commits.extend(pr_commits_records)
            except Exception as e:
                logger.warning(f"Failed to fetch commits for PR #{pr_number}: {e}")
                continue
    
    progress_bar.empty()
    return pd.DataFrame(all_commits)

def fetch_commits_from_prs(
    prs: pd.DataFrame, 
    owner: str, 
    repo: str
) -> pd.DataFrame:
    """Wrapper to maintain compatibility while using optimized version."""
    return fetch_commits_from_prs_optimized(prs, owner, repo)
    """Fetch commits for all PRs with proper error handling."""
    all_commits = []
    config = AppConfig()
    
    for _, pr_row in prs.iterrows():
        try:
            pr_number = pr_row['number']
            commits = _fetch_pr_commits_with_retry(
                pr_number, owner, repo, config.github.max_retries
            )
            
            if commits:
                pr_commits = _transform_commits_to_records(commits, pr_row)
                all_commits.extend(pr_commits)
                
        except GitHubAPIError as e:
            st.warning(f"Failed to fetch commits for PR #{pr_row['number']}: {e}")
            logger.warning(f"PR {pr_row['number']} commit fetch failed: {e}")
            continue
        except Exception as e:
            st.warning(f"Unexpected error for PR #{pr_row['number']}: {str(e)}")
            logger.error(f"Unexpected error for PR {pr_row['number']}: {e}")
            continue
    
    return pd.DataFrame(all_commits)

def _fetch_single_pr_commits_optimized(
    pr_number: int, 
    owner: str, 
    repo: str
) -> Optional[List[Dict[str, Any]]]:
    """Optimized single PR commit fetching with caching."""
    # Check cache first
    cache_key = f"commits_{pr_number}_{owner}_{repo}"
    cached_commits = get_cached_data(cache_key)
    if cached_commits is not None:
        return cached_commits
    
    commits_url_suffix = f"pulls/{pr_number}/commits"
    
    try:
        response = github_api_call(commits_url_suffix, owner, repo, use_rate_limit=False)
        commits = response.json()
        
        # Sanitize response data
        sanitized_commits = sanitize_api_response(commits)
        
        # Cache the result
        cache_data(cache_key, sanitized_commits)
        return sanitized_commits
        
    except GitHubAPIError:
        raise  # Re-raise GitHub API errors
    except Exception as e:
        logger.error(f"Failed to process commits for PR {pr_number}: {e}")
        return None

def fetch_commits_from_pr(
    pr_number: int, 
    owner: str, 
    repo: str
) -> Optional[List[Dict[str, Any]]]:
    """Fetch commits for a single PR."""
    commits_url_suffix = f"pulls/{pr_number}/commits"
    
    try:
        response = github_api_call(commits_url_suffix, owner, repo)
        commits = response.json()
        
        # Sanitize response data
        sanitized_commits = sanitize_api_response(commits)
        return sanitized_commits
        
    except GitHubAPIError:
        raise  # Re-raise GitHub API errors
    except Exception as e:
        logger.error(f"Failed to process commits for PR {pr_number}: {e}")
        return None
    
@performance_timer
@st.cache_data(ttl=1800)  # 30-minute cache for PRs
def fetch_prs_merged_between_dates_optimized(
    owner: str, 
    repo: str, 
    start_date: date, 
    end_date: date, 
    main_branch: str = 'main',
    max_pages: int = 10
) -> Tuple[Optional[pd.DataFrame], str]:
    """Optimized PR fetching with pagination and caching."""
    # Check cache first
    cache_key = get_cache_key(owner, repo, start_date, end_date, main_branch)
    cached_result = get_cached_data(cache_key)
    if cached_result is not None:
        return cached_result
    
    config = AppConfig()
    
    # Validate date range
    if start_date > end_date:
        raise ValidationError("Start date must be before end date")
    
    all_prs = []
    repo_description = ""
    page = 1
    
    # Fetch multiple pages with progress tracking
    progress_bar = st.progress(0)
    st.text("Fetching PRs with pagination...")
    
    while page <= max_pages:
        prs_url_suffix = "pulls"
        params = {
            "state": "closed",
            "base": main_branch,
            "sort": "updated",
            "direction": "desc",
            "per_page": config.github.per_page,
            "page": page
        }
        
        try:
            progress_bar.progress(min(page / max_pages, 0.9))
            response = github_api_call(prs_url_suffix, owner, repo, params)
            prs = response.json()
            
            if not prs:  # No more pages
                break
                
            # Sanitize response data
            prs = sanitize_api_response(prs)
            
            # Extract repo description from first page
            if page == 1 and prs and isinstance(prs, list) and len(prs) > 0:
                try:
                    head_data = prs[0].get('head', {})
                    repo_data = head_data.get('repo', {})
                    repo_description = repo_data.get('description', '')
                except (KeyError, IndexError, TypeError):
                    logger.warning("Could not extract repository description")
            
            # Quick pre-filter to avoid processing irrelevant PRs
            filtered_prs = []
            for pr in prs:
                if pr.get('merged_at'):
                    merged_date = pd.to_datetime(pr['merged_at']).date()
                    if start_date <= merged_date <= end_date:
                        filtered_prs.append(pr)
                    elif merged_date < start_date:
                        # Since PRs are sorted by updated time desc, 
                        # we can break early if we encounter older PRs
                        logger.info(f"Early termination at page {page} - found PR older than start_date")
                        page = max_pages + 1  # Break outer loop
                        break
            
            all_prs.extend(filtered_prs)
            
            # If we got fewer PRs than per_page, we've reached the end
            if len(prs) < config.github.per_page:
                break
                
            page += 1
            
        except GitHubAPIError:
            raise
        except Exception as e:
            error_msg = f"Failed to fetch PRs for {owner}/{repo} page {page}: {str(e)}"
            logger.error(error_msg)
            raise GitHubAPIError(error_msg)
    
    progress_bar.progress(1.0)
    progress_bar.empty()
    
    # Create DataFrame with better error handling
    if not all_prs:
        result = (pd.DataFrame(), repo_description)
    else:
        df = pd.DataFrame(all_prs)
        # Convert merged_at to datetime (already filtered, so all should have merged_at)
        df['merged_at'] = pd.to_datetime(df['merged_at'])
        result = (df, repo_description)
    
    # Cache the result
    cache_data(cache_key, result)
    return result

def fetch_prs_merged_between_dates(
    owner: str, 
    repo: str, 
    start_date: date, 
    end_date: date, 
    main_branch: str = 'main'
) -> Tuple[Optional[pd.DataFrame], str]:
    """Wrapper to maintain compatibility while using optimized version."""
    return fetch_prs_merged_between_dates_optimized(owner, repo, start_date, end_date, main_branch)
    """Fetch PRs merged between specified dates with improved error handling."""
    config = AppConfig()
    
    # Validate date range
    if start_date > end_date:
        raise ValidationError("Start date must be before end date")
    
    prs_url_suffix = "pulls"
    params = {
        "state": "closed",
        "base": main_branch,
        "sort": "updated",
        "direction": "desc",
        "per_page": config.github.per_page
    }
    
    try:
        response = github_api_call(prs_url_suffix, owner, repo, params)
        prs = response.json()
        
        # Sanitize response data
        prs = sanitize_api_response(prs)
        
        # Create DataFrame with better error handling
        df = pd.DataFrame(prs)
        
        if df.empty:
            return df, ""
        
        # Extract repo description safely
        repo_description = ""
        try:
            if prs and isinstance(prs, list) and len(prs) > 0:
                head_data = prs[0].get('head', {})
                repo_data = head_data.get('repo', {})
                repo_description = repo_data.get('description', '')
        except (KeyError, IndexError, TypeError):
            logger.warning("Could not extract repository description")
        
        # Filter for merged PRs with efficient pandas operations
        df = df.dropna(subset=['merged_at'])
        
        if df.empty:
            return df, repo_description
        
        # Convert merged_at to datetime
        df['merged_at'] = pd.to_datetime(df['merged_at'])
        
        # Filter by date range using vectorized operations
        mask = (
            (df['merged_at'].dt.date >= start_date) & 
            (df['merged_at'].dt.date <= end_date)
        )
        
        filtered_df = df[mask].copy()
        return filtered_df, repo_description
        
    except GitHubAPIError:
        raise  # Re-raise GitHub API errors
    except Exception as e:
        error_msg = f"Failed to fetch PRs for {owner}/{repo}: {str(e)}"
        logger.error(error_msg)
        raise GitHubAPIError(error_msg)


def _fetch_pr_commits_with_retry(
    pr_number: int, 
    owner: str, 
    repo: str, 
    max_retries: int
) -> Optional[List[Dict[str, Any]]]:
    """Fetch commits for a single PR with retry logic."""
    config = AppConfig()
    
    for attempt in range(max_retries):
        try:
            commits = fetch_commits_from_pr(pr_number, owner, repo)
            if commits is not None:
                return commits
        except GitHubAPIError as e:
            if attempt == max_retries - 1:
                raise e
            # Exponential backoff
            wait_time = config.github.rate_limit_delay * (2 ** attempt)
            time.sleep(wait_time)
            continue
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(config.github.rate_limit_delay)
            continue
    
    return None


def _transform_commits_to_records(
    commits: List[Dict[str, Any]], 
    pr_row: pd.Series
) -> List[Dict[str, Any]]:
    """Transform commits data to records format."""
    from utils.security import sanitize_commit_message
    
    records = []
    for commit in commits:
        if not isinstance(commit, dict):
            continue
            
        commit_data = commit.get('commit', {})
        message = commit_data.get('message', '')
        
        # Skip merge commits
        if message.startswith("Merge branch"):
            continue
            
        records.append({
            'PR Number': pr_row['number'],
            'PR Title': pr_row['title'],
            'Commit SHA': commit.get('sha', ''),
            'Commit Message': sanitize_commit_message(message)
        })
    
    return records
