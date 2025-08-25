import os
import logging
import time
import hashlib
import pickle
from typing import Optional, List
from openai import OpenAI
import pandas as pd
import streamlit as st
from functools import wraps

from config.settings import AppConfig, get_secure_openai_key
from config.exceptions import OpenAIAPIError
from utils.security import sanitize_commit_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance monitoring
def performance_timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"Performance: {func.__name__} took {end_time - start_time:.2f}s")
        return result
    return wrapper

# OpenAI response caching
OPENAI_CACHE_DIR = "/tmp/openai_cache"
OPENAI_CACHE_TTL = 7200  # 2 hours

def get_openai_cache_key(commits: str, start_date, end_date, owner: str, repo: str) -> str:
    """Generate cache key for OpenAI responses."""
    # Create hash of the commits content plus metadata
    key_data = f"{commits}{start_date}{end_date}{owner}{repo}"
    return hashlib.sha256(key_data.encode()).hexdigest()

def get_cached_openai_response(cache_key: str) -> Optional[str]:
    """Get cached OpenAI response if valid."""
    os.makedirs(OPENAI_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(OPENAI_CACHE_DIR, f"{cache_key}.pkl")
    
    try:
        if os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            if time.time() - cache_time < OPENAI_CACHE_TTL:
                with open(cache_file, 'rb') as f:
                    logger.info(f"OpenAI cache hit: {cache_key[:12]}...")
                    return pickle.load(f)
            else:
                os.remove(cache_file)
                logger.info(f"OpenAI cache expired: {cache_key[:12]}...")
    except Exception as e:
        logger.warning(f"OpenAI cache read error: {e}")
    
    return None

def cache_openai_response(cache_key: str, response: str) -> None:
    """Cache OpenAI response."""
    os.makedirs(OPENAI_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(OPENAI_CACHE_DIR, f"{cache_key}.pkl")
    
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(response, f)
        logger.info(f"OpenAI response cached: {cache_key[:12]}...")
    except Exception as e:
        logger.warning(f"OpenAI cache write error: {e}")

def validate_and_enhance_changelog(changelog: str, owner: str, repo: str) -> str:
    """Validate changelog structure and enhance formatting for CloudFix context."""
    import re
    from datetime import datetime
    
    # Basic validation
    if not changelog or len(changelog.strip()) < 50:
        logger.warning("Generated changelog too short, creating fallback")
        return create_fallback_changelog(owner, repo)
    
    # Ensure proper header format
    current_date = datetime.now().strftime("%Y-%m-%d")
    if not re.search(r'##\s*\[.*?\]\s*-\s*\d{4}-\d{2}-\d{2}', changelog):
        # Add proper header if missing
        changelog = f"## [Unreleased] - {current_date}\n\n" + changelog.lstrip('#').lstrip()
    
    # Ensure required sections exist
    required_sections = ['Added', 'Changed', 'Fixed']
    for section in required_sections:
        # Check for emoji or plain section headers
        section_patterns = [
            f'### ✨ {section}',
            f'### 🔧 {section}' if section == 'Changed' else f'### 🐛 {section}' if section == 'Fixed' else f'### ✨ {section}',
            f'### {section}'
        ]
        
        has_section = any(pattern in changelog for pattern in section_patterns)
        if not has_section and section == 'Changed':
            # Add empty Changed section if missing (most common)
            insert_pos = changelog.find('### 🐛 Fixed') if '### 🐛 Fixed' in changelog else len(changelog)
            changelog = changelog[:insert_pos] + f"\n### 🔧 Changed\n- Internal improvements to system reliability and performance\n\n" + changelog[insert_pos:]
    
    # Ensure CloudFix branding context
    if 'CloudFix' not in changelog and 'AWS cost' not in changelog:
        # Add CloudFix context to first section
        first_entry_match = re.search(r'(### [^\n]+\n)([^#]*)', changelog)
        if first_entry_match:
            section_header = first_entry_match.group(1)
            section_content = first_entry_match.group(2)
            if section_content.strip() and not section_content.strip().startswith('- Internal improvements'):
                # Already has good content, keep it
                pass
            else:
                # Replace with CloudFix-specific content
                enhanced_content = "- Enhanced AWS cost optimization capabilities and platform reliability\n"
                changelog = changelog.replace(first_entry_match.group(0), section_header + enhanced_content)
    
    # Validate PR references
    lines = changelog.split('\n')
    enhanced_lines = []
    for line in lines:
        if line.strip().startswith('- ') and '[#' not in line and line.strip() != '- Internal improvements to system reliability and performance':
            # Add generic PR reference if missing
            line = line.rstrip() + ' [#PR]'
        enhanced_lines.append(line)
    
    return '\n'.join(enhanced_lines)

def create_fallback_changelog(owner: str, repo: str) -> str:
    """Create a fallback changelog when AI generation fails or produces poor output."""
    from datetime import datetime
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    return f"""## [Unreleased] - {current_date}

### 🔧 Changed
- Internal improvements to system reliability and performance
- Enhanced AWS cost optimization capabilities
- Various bug fixes and stability improvements

### 🐛 Fixed
- Resolved issues affecting platform performance
- Improved error handling and user experience

_Note: This changelog was automatically generated. For detailed changes, please review the pull request history._"""

def estimate_token_count(text: str) -> int:
    """Rough estimation of token count (1 token ≈ 4 characters)."""
    return len(text) // 4

def truncate_commits_intelligently(commits: str, max_tokens: int) -> str:
    """Intelligently truncate commits while preserving important information."""
    max_chars = max_tokens * 4
    
    if len(commits) <= max_chars:
        return commits
    
    # Split by PR sections and prioritize recent/important changes
    pr_sections = commits.split('PR #')
    if len(pr_sections) <= 1:
        return commits[:max_chars] + "\n\n... (truncated)"
    
    # Keep first section (header) and as many PR sections as possible
    result = pr_sections[0]
    remaining_chars = max_chars - len(result)
    
    for i, section in enumerate(pr_sections[1:], 1):
        section_with_pr = 'PR #' + section
        if len(result) + len(section_with_pr) > max_chars:
            result += "\n\n... (additional changes truncated)"
            break
        result += section_with_pr
    
    return result

def generate_changelog_single_step(client, config, system_prompt: str, user_prompt: str) -> str:
    """Generate changelog in a single API call."""
    response = client.chat.completions.create(
        model=config.openai.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,  # Lower temperature for consistent output
        max_tokens=config.openai.max_tokens or 2000,
        timeout=config.openai.timeout
    )
    
    if not response.choices or not response.choices[0].message.content:
        raise OpenAIAPIError("Invalid response from OpenAI API")
    
    return response.choices[0].message.content

def generate_changelog_with_reasoning(client, config, system_prompt: str, user_prompt: str) -> str:
    """Generate changelog using multi-step reasoning for complex repositories."""
    
    # Step 1: Analysis and categorization
    analysis_prompt = user_prompt + "\n\n## STEP 1: ANALYSIS\nFirst, analyze all the changes and categorize them. For each PR, identify:\n1. Category (Added/Changed/Fixed/Security)\n2. User impact (High/Medium/Low)\n3. AWS cost optimization relevance\n4. Brief description\n\nProvide your analysis in a structured format."
    
    analysis_response = client.chat.completions.create(
        model=config.openai.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": analysis_prompt}
        ],
        temperature=0.2,
        max_tokens=1500,
        timeout=config.openai.timeout
    )
    
    if not analysis_response.choices:
        # Fallback to single step
        return generate_changelog_single_step(client, config, system_prompt, user_prompt)
    
    analysis = analysis_response.choices[0].message.content
    
    # Step 2: Changelog generation based on analysis
    final_prompt = f"""Based on your analysis below, now create the final changelog following the exact format specified in the system prompt.

## Your Analysis:
{analysis}

## STEP 2: FINAL CHANGELOG
Now create the properly formatted changelog with emoji headers and proper entries."""
    
    final_response = client.chat.completions.create(
        model=config.openai.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.1,  # Very low temperature for final formatting
        max_tokens=1500,
        timeout=config.openai.timeout
    )
    
    if not final_response.choices or not final_response.choices[0].message.content:
        # Fallback to analysis content if final step fails
        return analysis if analysis else "Failed to generate changelog"
    
    return final_response.choices[0].message.content

@performance_timer
@st.cache_data(ttl=3600)
def extract_messages_from_commits_optimized(pr_commit_data: pd.DataFrame) -> str:
    """Optimized commit message extraction with caching and vectorized operations."""
    if pr_commit_data.empty:
        return ""
    
    # Filter out merge commits early using vectorized operations
    mask = ~pr_commit_data['Commit Message'].str.startswith("Merge branch", na=False)
    filtered_data = pr_commit_data[mask]
    
    if filtered_data.empty:
        return ""
    
    # Group by PR more efficiently
    grouped = filtered_data.groupby(['PR Number', 'PR Title']).agg({
        'Commit Message': list
    }).reset_index()
    
    overall_text = []
    for _, row in grouped.iterrows():
        pr_text = [f"PR #{row['PR Number']}: {row['PR Title']}"]
        pr_text.extend([f"- {msg}" for msg in row['Commit Message']])
        overall_text.append("\n".join(pr_text))
        
    return "\n\n".join(overall_text)

def extract_messages_from_commits(pr_commit_data: pd.DataFrame) -> str:
    """Wrapper for compatibility."""
    return extract_messages_from_commits_optimized(pr_commit_data)
    """Groups commit messages by PR and formats them for the changelog"""
    
    commits_by_pr = {}
    for _, row in pr_commit_data.iterrows():
        pr_title = row['PR Title']
        commit_msg = row['Commit Message']
        pr_number = row['PR Number']
        
        if commit_msg.startswith("Merge branch"):
            continue
            
        if pr_title not in commits_by_pr:
            commits_by_pr[pr_title] = {
                'number': pr_number,
                'commits': []
            }
        commits_by_pr[pr_title]['commits'].append(commit_msg)
    
    overall_text = []
    for pr_title, data in commits_by_pr.items():
        pr_text = [f"PR #{data['number']}: {pr_title}"]
        pr_text.extend([f"- {msg}" for msg in data['commits']])
        overall_text.append("\n".join(pr_text))
        
    return "\n\n".join(overall_text)

@performance_timer
def gpt_inference_changelog_optimized(
    commits: str, 
    start_date, 
    end_date, 
    owner: str, 
    repo: str, 
    repo_description: str, 
    main_branch: List[str]
) -> Optional[str]:
    """Optimized changelog generation with caching and improved prompts."""
    
    # Check cache first
    cache_key = get_openai_cache_key(commits, start_date, end_date, owner, repo)
    cached_response = get_cached_openai_response(cache_key)
    if cached_response:
        st.info("✅ Using cached changelog (saves API costs!)")
        return cached_response
    
    # CloudFix-optimized system prompt with few-shot examples and structured reasoning
    system_prompt = """You are a technical writer specializing in AWS cost optimization and infrastructure management. You're creating a professional changelog for CloudFix, an AWS cost optimization platform used by DevOps teams and FinOps professionals.

# TASK OVERVIEW
Create a structured, email-ready changelog that communicates value to CloudFix users who manage AWS infrastructure costs.

# OUTPUT FORMAT
Use this exact structure with proper markdown:

## [Unreleased] - {current_date}

### ✨ Added
- New AWS cost optimization features
- Enhanced monitoring and alerting capabilities
- Additional AWS service integrations

### 🔧 Changed  
- Improvements to existing cost analysis features
- Enhanced user experience and performance optimizations
- Updated AWS service compatibility

### 🐛 Fixed
- Resolved cost calculation issues
- Bug fixes affecting AWS resource monitoring
- Performance and reliability improvements

### 🔒 Security
- AWS IAM and security enhancements
- Data protection and compliance updates

# CONTENT RULES

## 1. CloudFix Context Prioritization
- **AWS Cost Savings**: Emphasize financial impact ("Reduces costs by X%", "Saves $Y monthly")
- **AWS Services**: Focus on AWS service integrations (EC2, RDS, Lambda, etc.)
- **Infrastructure Impact**: Highlight changes affecting AWS resource management
- **User Workflow**: Prioritize features affecting daily FinOps/DevOps workflows

## 2. Language Guidelines
- Use business-friendly language for financial impact
- Explain AWS service benefits in plain terms
- Focus on "what this means for your AWS bill"
- Use active voice: "Improved cost tracking" not "Cost tracking was improved"

## 3. Categorization Rules
- **Added**: New cost optimization features, AWS service support, monitoring capabilities
- **Changed**: Enhanced existing features, improved algorithms, UI/UX updates
- **Fixed**: Cost calculation bugs, AWS API issues, performance problems
- **Security**: AWS IAM changes, compliance features, data protection

## 4. Email Optimization
- Maximum 2 lines per entry for email readability
- Lead with business value, follow with technical detail
- Use bullet points that scan quickly
- Include measurable impact when possible

## 5. Quality Standards
- Include PR reference as [#123] at end of each entry
- Skip internal refactoring unless it improves cost optimization
- Group related AWS services together
- Order by potential cost impact (highest savings first)

# EXAMPLES OF GOOD ENTRIES

### ✨ Added
- Enhanced EC2 rightsizing recommendations with machine learning analysis, improving cost savings accuracy by up to 25% [#156]
- Real-time AWS Lambda cost monitoring with automated alerting for usage spikes above configurable thresholds [#142]

### 🔧 Changed
- Improved RDS cost optimization algorithm to better handle multi-AZ deployments, reducing false positive recommendations [#189]
- Updated cost dashboard with clearer visualization of potential monthly savings across AWS services [#175]

### 🐛 Fixed
- Resolved S3 storage class cost calculations for objects with complex lifecycle policies [#203]
- Fixed CloudWatch costs not appearing correctly in cross-region analysis reports [#198]

### 🔒 Security
- Enhanced AWS IAM role validation with stricter permission checks for cost optimization actions [#167]

# EXAMPLES OF BAD ENTRIES (AVOID THESE)
- Updated dependencies (too technical, no user value)
- Fixed typo in documentation (trivial change)
- Refactored internal API structure (internal change)
- Added unit tests for service layer (developer-focused)

# EDGE CASE HANDLING
- If no user-facing changes found, create: "### 🔧 Changed\n- Internal improvements to system reliability and performance [multiple PRs]"
- If only bug fixes, emphasize reliability: "Enhanced platform stability"
- Group multiple small related changes: "Various improvements to AWS cost calculation accuracy"

# CHAIN-OF-THOUGHT PROCESS
Before writing each entry, consider:
1. Does this change affect AWS cost optimization?
2. Will CloudFix users see/feel this change?
3. Can I quantify the business impact?
4. How does this improve their AWS cost management?
5. What category best represents the user value?

Write entries that make CloudFix users think: "This will help me save money on AWS" or "This makes managing my AWS costs easier."""

    # Handle multiple branches more elegantly
    branch_info = ', '.join(main_branch) if isinstance(main_branch, list) else str(main_branch)
    
    # CloudFix-specific user prompt with structured reasoning
    user_prompt = f"""# CHANGELOG GENERATION REQUEST

## Repository Context
**Repository**: {owner}/{repo}
**Description**: {repo_description}
**Platform**: CloudFix AWS Cost Optimization Platform
**Time Period**: {start_date} to {end_date}
**Branches**: {branch_info}

## Target Audience
CloudFix users including:
- FinOps teams managing AWS costs
- DevOps engineers optimizing infrastructure
- Engineering managers tracking cost efficiency
- AWS infrastructure architects

## Changes to Analyze
{commits}

## ANALYSIS INSTRUCTIONS

### Step 1: Filter for User Impact
Identify changes that affect:
- AWS cost optimization capabilities
- User interface and experience
- Cost calculation accuracy
- AWS service integrations
- Performance affecting cost analysis
- Security/compliance features

### Step 2: Categorize by Business Value
For each user-impacting change, determine:
- Primary category (Added/Changed/Fixed/Security)
- AWS cost impact (direct savings, better analysis, etc.)
- User workflow improvement
- Technical enhancement with business benefit

### Step 3: Write Customer-Focused Entries
For each entry:
1. Lead with business value/user benefit
2. Explain AWS cost optimization impact
3. Use clear, non-technical language
4. Include measurable impact when possible
5. Add PR reference [#XXX]

### Step 4: Quality Check
- Does each entry answer "How does this help users save money or manage AWS costs better?"
- Are entries email-scannable (concise, clear value)
- Are similar changes grouped logically
- Is the most impactful content listed first

### EDGE CASE HANDLING
If you find:
- Only internal/technical changes → Focus on reliability/performance benefits
- No clear user changes → Create generic "system improvements" entry
- Unclear business impact → Categorize as "Changed" with general improvement language
- Security-only changes → Emphasize trust and compliance value

Generate a changelog that makes CloudFix users excited about cost optimization improvements and confident in platform reliability."""

    config = AppConfig()
    api_key = get_secure_openai_key()
    
    if not api_key:
        st.error("OpenAI API key is required")
        return None
        
    client = OpenAI(api_key=api_key)
    
    try:
        logger.info(f"Generating changelog for {owner}/{repo} (cache miss)")
        st.info("🤖 Generating changelog with AI...")
        
        # Add progress indicator
        progress = st.progress(0)
        progress.progress(0.3)
        
        # Check token count and truncate if necessary
        total_prompt_tokens = estimate_token_count(system_prompt + user_prompt)
        max_input_tokens = 15000  # Conservative limit for input
        
        if total_prompt_tokens > max_input_tokens:
            logger.warning(f"Prompt too long ({total_prompt_tokens} tokens), truncating commits")
            # Extract commits from user_prompt and truncate
            commits_match = user_prompt.find('**Changes to Analyze**:')
            if commits_match != -1:
                commits_start = commits_match + len('**Changes to Analyze**:\n')
                commits_end = user_prompt.find('\n\n## ANALYSIS INSTRUCTIONS', commits_start)
                if commits_end == -1:
                    commits_end = len(user_prompt)
                original_commits = user_prompt[commits_start:commits_end].strip()
                truncated_commits = truncate_commits_intelligently(original_commits, max_input_tokens - estimate_token_count(system_prompt) - 500)
                user_prompt = user_prompt[:commits_start] + truncated_commits + user_prompt[commits_end:]
        
        progress.progress(0.5)
        
        # Multi-step reasoning approach for complex repositories
        if len(commits.split('PR #')) > 20:  # Many PRs, use two-step approach
            raw_changelog = generate_changelog_with_reasoning(client, config, system_prompt, user_prompt)
        else:
            # Single-step approach for simpler cases
            raw_changelog = generate_changelog_single_step(client, config, system_prompt, user_prompt)
        
        progress.progress(0.8)
        
        if not raw_changelog:
            raise OpenAIAPIError("Empty response from OpenAI API")
        
        # Validate and enhance changelog structure
        changelog = validate_and_enhance_changelog(raw_changelog, owner, repo)
        
        progress.progress(1.0)
        progress.empty()
        
        # Cache the successful response
        cache_openai_response(cache_key, changelog)
        
        logger.info("Changelog generated successfully")
        st.success("✅ Changelog generated!")
        return changelog
        
    except Exception as e:
        error_msg = f"Error generating changelog: {str(e)}"
        logger.error(error_msg)
        
        # Attempt to create fallback changelog
        try:
            st.warning("AI generation failed, creating fallback changelog...")
            fallback_changelog = create_fallback_changelog(owner, repo)
            cache_openai_response(cache_key, fallback_changelog)
            return fallback_changelog
        except Exception as fallback_error:
            logger.error(f"Fallback changelog creation failed: {fallback_error}")
            st.error(error_msg)
            raise OpenAIAPIError(error_msg) from e

def gpt_inference_changelog(
    commits: str, 
    start_date, 
    end_date, 
    owner: str, 
    repo: str, 
    repo_description: str, 
    main_branch: List[str]
) -> Optional[str]:
    """Wrapper for compatibility."""
    return gpt_inference_changelog_optimized(commits, start_date, end_date, owner, repo, repo_description, main_branch)
    """Generates a changelog using GPT-4o"""
    
    system_prompt = """Create a changelog from git commits following these rules:
    1. Group changes into sections: Added, Changed, Deprecated, Removed, Fixed, Security
    2. Keep entries clear and concise
    3. Include PR numbers as links [#123]
    4. Focus on user-facing changes. This summary will be made available to external end-users and customers
    5. Use active voice
    6. Start each entry with a verb (Added, Fixed, etc.)"""

    # Handle multiple branches
    branch_info = ', '.join(main_branch) if isinstance(main_branch, list) else str(main_branch)
    
    user_prompt = f"""Generate a changelog for {owner}/{repo} ({repo_description}) 
    Time period: {start_date} to {end_date}
    Branches: {branch_info}

    Commit messages:
    {commits}"""

    config = AppConfig()
    api_key = get_secure_openai_key()
    
    if not api_key:
        st.error("OpenAI API key is required")
        return None
        
    client = OpenAI(api_key=api_key)
    
    try:
        logger.info(f"Generating changelog for {owner}/{repo}")
        
        response = client.chat.completions.create(
            model=config.openai.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=config.openai.temperature,
            max_tokens=config.openai.max_tokens,
            timeout=config.openai.timeout
        )
        
        if not response.choices:
            raise OpenAIAPIError("No response from OpenAI API")
            
        changelog = response.choices[0].message.content
        
        if not changelog:
            raise OpenAIAPIError("Empty response from OpenAI API")
        
        logger.info("Changelog generated successfully")
        return changelog
        
    except Exception as e:
        error_msg = f"Error generating changelog: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        raise OpenAIAPIError(error_msg) from e