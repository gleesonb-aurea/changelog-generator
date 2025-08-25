#!/usr/bin/env python3
"""
API wrapper for the CloudFix changelog generator.
Exposes the Streamlit app functionality as a REST API for n8n integration.
"""

from flask import Flask, request, jsonify
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.github_data_fetch import fetch_prs_merged_between_dates, fetch_commits_from_prs
from utils.summarisation import gpt_inference_changelog, extract_messages_from_commits
from utils.security import validate_repository_url, sanitize_commit_message
from config.settings import validate_configuration
from config.exceptions import GitHubAPIError, OpenAIAPIError, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# API configuration
API_TOKEN = os.getenv('CHANGELOG_API_TOKEN', 'your-secure-api-token')
ALLOWED_REPOS = [
    'trilogy-group/cloudfix-aws',
    # Add other allowed repositories here
]

def authenticate_request() -> bool:
    """Validate API token from request headers."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header[7:]  # Remove 'Bearer ' prefix
    return token == API_TOKEN

def validate_repository_access(owner: str, repo: str) -> bool:
    """Check if repository is in allowed list."""
    repo_path = f"{owner}/{repo}"
    return repo_path in ALLOWED_REPOS

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

@app.route('/generate', methods=['POST'])
def generate_changelog():
    """Generate changelog API endpoint."""
    
    # Authenticate request
    if not authenticate_request():
        return jsonify({
            'success': False,
            'error': 'Unauthorized - Invalid API token'
        }), 401
    
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid JSON payload'
            }), 400
        
        # Extract and validate parameters
        owner = data.get('owner', 'trilogy-group')
        repo = data.get('repo', 'cloudfix-aws')
        branches = data.get('branches', ['production'])
        days_back = data.get('days_back', 30)
        output_format = data.get('format', 'markdown')  # 'markdown' or 'email'
        
        # Validate repository access
        if not validate_repository_access(owner, repo):
            return jsonify({
                'success': False,
                'error': f'Repository {owner}/{repo} not authorized'
            }), 403
        
        # Validate configuration (API keys, etc.)
        try:
            validate_configuration()
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return jsonify({
                'success': False,
                'error': 'API configuration error - check server logs'
            }), 500
        
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"Generating changelog for {owner}/{repo} from {start_date} to {end_date}")
        
        # Fetch PRs for all branches
        all_prs = []
        repo_description = ""
        
        for branch in branches:
            try:
                branch_prs, repo_desc = fetch_prs_merged_between_dates(
                    owner, repo, start_date, end_date, branch
                )
                if branch_prs is not None and not branch_prs.empty:
                    branch_prs['branch'] = branch
                    all_prs.append(branch_prs)
                    if not repo_description and repo_desc:
                        repo_description = repo_desc
                        
            except Exception as e:
                logger.warning(f"Failed to fetch PRs for branch {branch}: {e}")
                continue
        
        if not all_prs:
            # No PRs found - return a friendly message
            fallback_content = generate_fallback_changelog(owner, repo, start_date, end_date)
            return jsonify({
                'success': True,
                'changelog': fallback_content['content'],
                'summary': fallback_content['summary'],
                'pr_count': 0,
                'commit_count': 0,
                'branches': branches,
                'date_range': f"{start_date} to {end_date}"
            })
        
        # Combine all PRs
        import pandas as pd
        prs = pd.concat(all_prs, ignore_index=True)
        
        # Fetch commits
        commits = fetch_commits_from_prs(prs, owner, repo)
        
        # Extract and process commit messages
        messages = extract_messages_from_commits(commits)
        
        # Generate changelog
        changelog = gpt_inference_changelog(
            messages, start_date, end_date, owner, repo, repo_description, branches
        )
        
        if not changelog:
            fallback_content = generate_fallback_changelog(owner, repo, start_date, end_date)
            return jsonify({
                'success': True,
                'changelog': fallback_content['content'],
                'summary': fallback_content['summary'],
                'pr_count': len(prs),
                'commit_count': len(commits),
                'branches': branches,
                'date_range': f"{start_date} to {end_date}",
                'fallback': True
            })
        
        # Format for email if requested
        if output_format == 'email':
            changelog = format_for_email(changelog)
        
        # Generate summary
        summary = generate_summary(prs, commits, changelog)
        
        return jsonify({
            'success': True,
            'changelog': changelog,
            'summary': summary,
            'pr_count': len(prs),
            'commit_count': len(commits),
            'branches': branches,
            'date_range': f"{start_date} to {end_date}"
        })
        
    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {e}")
        return jsonify({
            'success': False,
            'error': f'GitHub API error: {str(e)}',
            'error_type': 'github_api'
        }), 500
        
    except OpenAIAPIError as e:
        logger.error(f"OpenAI API error: {e}")
        return jsonify({
            'success': False,
            'error': f'OpenAI API error: {str(e)}',
            'error_type': 'openai_api'
        }), 500
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Validation error: {str(e)}',
            'error_type': 'validation'
        }), 400
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error - check logs',
            'error_type': 'internal'
        }), 500

def generate_fallback_changelog(owner: str, repo: str, start_date, end_date) -> Dict[str, str]:
    """Generate a fallback changelog when no data is available."""
    month_year = end_date.strftime('%B %Y')
    
    content = f"""## CloudFix Updates - {month_year}

### 🔧 Platform Improvements
- Continued enhancements to AWS cost optimization algorithms
- Performance improvements across the platform
- Security updates and maintenance

### 📊 Behind the Scenes
- Infrastructure scaling and reliability improvements
- Enhanced monitoring and alerting systems
- Preparation for upcoming feature releases

*For the most up-to-date information, visit our [GitHub repository](https://github.com/{owner}/{repo}) or contact our support team.*
"""
    
    summary = f"""We've been working hard on platform improvements this {month_year.lower()}. While there were no major feature releases, our team focused on infrastructure enhancements, security updates, and preparing for exciting new features coming soon."""
    
    return {
        'content': content,
        'summary': summary
    }

def format_for_email(changelog: str) -> str:
    """Format changelog content optimally for email."""
    # Convert markdown headers to HTML for better email rendering
    lines = changelog.split('\n')
    formatted_lines = []
    
    for line in lines:
        if line.startswith('## '):
            # Main heading
            formatted_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith('### '):
            # Section heading
            icon_map = {
                'Added': '✨',
                'Changed': '🔧', 
                'Fixed': '🐛',
                'Security': '🔒',
                'Removed': '🗑️',
                'Deprecated': '⚠️'
            }
            section_name = line[4:].strip()
            icon = icon_map.get(section_name, '📋')
            formatted_lines.append(f"<h3>{icon} {section_name}</h3>")
        elif line.startswith('- '):
            # List item
            formatted_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip():
            # Regular paragraph
            formatted_lines.append(f"<p>{line}</p>")
        else:
            formatted_lines.append("")
    
    # Wrap lists in ul tags
    in_list = False
    final_lines = []
    
    for line in formatted_lines:
        if line.startswith('<li>') and not in_list:
            final_lines.append('<ul>')
            final_lines.append(line)
            in_list = True
        elif line.startswith('<li>') and in_list:
            final_lines.append(line)
        elif not line.startswith('<li>') and in_list:
            final_lines.append('</ul>')
            final_lines.append(line)
            in_list = False
        else:
            final_lines.append(line)
    
    if in_list:
        final_lines.append('</ul>')
    
    return '\n'.join(final_lines)

def generate_summary(prs, commits, changelog: str) -> str:
    """Generate a brief summary for the email."""
    
    # Count different types of changes
    lines = changelog.lower().split('\n')
    
    features = sum(1 for line in lines if 'added' in line or 'new' in line)
    fixes = sum(1 for line in lines if 'fixed' in line or 'resolved' in line)
    improvements = sum(1 for line in lines if 'improved' in line or 'enhanced' in line)
    
    total_changes = len(prs)
    
    if total_changes == 0:
        return "Our development team has been working on infrastructure improvements and preparing for upcoming releases."
    
    summary_parts = []
    
    if features > 0:
        summary_parts.append(f"{features} new feature{'s' if features != 1 else ''}")
    if fixes > 0:
        summary_parts.append(f"{fixes} bug fix{'es' if fixes != 1 else ''}")
    if improvements > 0:
        summary_parts.append(f"{improvements} improvement{'s' if improvements != 1 else ''}")
    
    if summary_parts:
        changes_text = ", ".join(summary_parts[:-1])
        if len(summary_parts) > 1:
            changes_text += f" and {summary_parts[-1]}"
        else:
            changes_text = summary_parts[0]
            
        return f"This month's CloudFix update includes {changes_text} across {total_changes} pull request{'s' if total_changes != 1 else ''}. We're continuing to enhance your AWS cost optimization experience with improved performance, new capabilities, and important fixes."
    else:
        return f"This month we processed {total_changes} update{'s' if total_changes != 1 else ''} focused on platform improvements, security enhancements, and infrastructure optimizations to serve you better."

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    # Verify required environment variables
    required_env_vars = ['GITHUB_API_KEY', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Start the Flask app
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting CloudFix Changelog API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)