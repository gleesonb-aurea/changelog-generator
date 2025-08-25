"""Security utilities for the changelog generator."""

import re
from typing import List, Dict, Any
from urllib.parse import urlparse


def sanitize_commit_message(message: str) -> str:
    """Remove potential PII from commit messages."""
    if not isinstance(message, str):
        return str(message)
    
    # Remove email addresses
    message = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
        '[EMAIL_REMOVED]', 
        message
    )
    
    # Remove potential IP addresses
    message = re.sub(
        r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', 
        '[IP_REMOVED]', 
        message
    )
    
    # Remove potential API keys or secrets (basic patterns)
    message = re.sub(
        r'\b[A-Za-z0-9]{32,}\b', 
        '[POTENTIAL_SECRET_REMOVED]', 
        message
    )
    
    # Remove URLs that might contain sensitive parameters
    message = re.sub(
        r'https?://[^\s<>"]+', 
        '[URL_REMOVED]', 
        message
    )
    
    return message


def sanitize_api_response(data: Any) -> Any:
    """Sanitize API response data to prevent injection."""
    if isinstance(data, dict):
        # Define allowed keys to prevent injection
        allowed_keys = {
            'title', 'number', 'merged_at', 'sha', 
            'commit', 'message', 'head', 'repo', 'description',
            'state', 'base', 'created_at', 'updated_at'
        }
        
        return {
            k: sanitize_api_response(v) 
            for k, v in data.items() 
            if k in allowed_keys
        }
    
    elif isinstance(data, list):
        return [sanitize_api_response(item) for item in data]
    
    elif isinstance(data, str):
        # Remove potentially dangerous characters
        return re.sub(r'[<>"\';\\]', '', data)
    
    return data


def validate_repository_url(url: str) -> tuple[str, str]:
    """Enhanced GitHub URL validation with security checks."""
    if not url or len(url) > 200:  # Reasonable length limit
        raise ValueError("Invalid URL length")
    
    try:
        parsed = urlparse(url)
        
        # Only allow HTTPS
        if parsed.scheme != 'https':
            raise ValueError("Only HTTPS URLs are allowed")
        
        # Only allow github.com
        if parsed.netloc != 'github.com':
            raise ValueError("Only github.com URLs are allowed")
        
        # More restrictive pattern for repo paths
        pattern = r'^/([a-zA-Z0-9]([a-zA-Z0-9\-]){0,38})/([a-zA-Z0-9\-\._]{1,100})/?$'
        match = re.match(pattern, parsed.path)
        
        if not match:
            raise ValueError("Invalid repository URL format")
        
        owner, repo = match.groups()[:2]
        
        # Additional security checks
        blocked_patterns = ['admin', 'api', 'www', 'root', 'system']
        if any(pattern in owner.lower() for pattern in blocked_patterns):
            raise ValueError("Repository owner contains blocked pattern")
        
        return owner, repo
        
    except Exception as e:
        raise ValueError(f"Invalid repository URL: {str(e)}")


def filter_sensitive_logs(log_message: str) -> str:
    """Filter sensitive information from log messages."""
    # Remove tokens/keys
    log_message = re.sub(r'(token|key|secret)=[^\s&]+', r'\1=[REDACTED]', log_message, flags=re.IGNORECASE)
    
    # Remove authorization headers
    log_message = re.sub(r'Authorization:\s*Bearer\s+[^\s]+', 'Authorization: Bearer [REDACTED]', log_message, flags=re.IGNORECASE)
    
    # Remove URLs with potential sensitive parameters
    log_message = re.sub(r'https://[^\s]+\?[^\s]+', '[URL_WITH_PARAMS_REDACTED]', log_message)
    
    return log_message


def show_privacy_notice() -> bool:
    """Display privacy notice and get user consent."""
    import streamlit as st
    
    with st.expander("🔒 Privacy Notice - Please Read", expanded=False):
        st.markdown("""
        **Data Processing Notice:**
        
        - This application processes git commit messages and repository metadata
        - Data is sent to OpenAI's GPT-4 service for changelog generation
        - We filter personal information, but please review your data carefully
        - No data is permanently stored by this application
        - Generated changelogs are temporary and can be deleted after use
        
        **Data We Process:**
        - Repository names and descriptions
        - Pull request titles and numbers
        - Commit messages (with PII filtering applied)
        - Merge dates and branch information
        
        **Third-Party Services:**
        - GitHub API (for repository data)
        - OpenAI API (for changelog generation)
        
        **Your Rights:**
        - You can stop processing at any time
        - Generated content is not stored permanently
        - Contact repository maintainer for privacy concerns
        """)
    
    consent = st.checkbox(
        "I understand and consent to the data processing described above", 
        key="privacy_consent"
    )
    
    if consent:
        st.success("✅ Privacy consent granted")
    else:
        st.warning("⚠️ Privacy consent required to proceed")
    
    return consent