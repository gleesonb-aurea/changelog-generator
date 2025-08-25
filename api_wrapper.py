"""
FastAPI wrapper for the changelog generator to expose REST API endpoints.
This enables n8n workflow integration.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime, timedelta
import logging
import os
import json
import asyncio
from contextlib import asynccontextmanager

# Import existing changelog functionality
from utils.github_data_fetch import (
    fetch_prs_merged_between_dates_optimized,
    fetch_commits_from_prs_optimized
)
from utils.summarisation import (
    extract_messages_from_commits_optimized,
    gpt_inference_changelog_optimized
)
from config.settings import AppConfig
from config.exceptions import GitHubAPIError, OpenAIAPIError, ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Request/Response Models
class ChangelogRequest(BaseModel):
    repository: str = Field(..., example="trilogy-group/cloudfix-aws")
    start_date: date = Field(..., example="2024-01-01")
    end_date: date = Field(..., example="2024-01-31")
    branches: List[str] = Field(default=["production"], example=["production", "main"])
    format: str = Field(default="markdown", enum=["markdown", "html", "json"])
    email_format: bool = Field(default=False, description="Format for email distribution")

class ChangelogResponse(BaseModel):
    success: bool
    changelog: Optional[str] = None
    summary: Optional[str] = None
    html_content: Optional[str] = None
    plain_text: Optional[str] = None
    metadata: dict = {}
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    dependencies: dict

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting CloudFix Changelog API")
    yield
    # Shutdown
    logger.info("Shutting down CloudFix Changelog API")

app = FastAPI(
    title="CloudFix Changelog Generator API",
    description="API for automated changelog generation and email distribution",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_repository_url(repository: str) -> tuple[str, str]:
    """Parse repository URL to extract owner and repo name."""
    try:
        if repository.startswith("https://github.com/"):
            parts = repository.replace("https://github.com/", "").strip("/").split("/")
        else:
            parts = repository.strip("/").split("/")
        
        if len(parts) >= 2:
            return parts[0], parts[1]
        else:
            raise ValueError("Invalid repository format")
    except Exception:
        raise HTTPException(
            status_code=400, 
            detail="Invalid repository format. Use 'owner/repo' or full GitHub URL"
        )

def format_for_email(changelog: str, metadata: dict) -> tuple[str, str]:
    """Format changelog for email distribution."""
    
    # HTML version with styling
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CloudFix Monthly Changelog</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .container {{
                background-color: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #007acc;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .logo {{
                font-size: 28px;
                font-weight: bold;
                color: #007acc;
                margin-bottom: 10px;
            }}
            .subtitle {{
                color: #666;
                font-size: 16px;
            }}
            h2 {{
                color: #007acc;
                border-left: 4px solid #007acc;
                padding-left: 15px;
                margin-top: 30px;
            }}
            h3 {{
                color: #555;
                margin-top: 25px;
            }}
            ul {{
                padding-left: 0;
                list-style: none;
            }}
            li {{
                background: #f8f9fa;
                margin: 8px 0;
                padding: 12px 15px;
                border-left: 3px solid #007acc;
                border-radius: 4px;
            }}
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                text-align: center;
                color: #666;
                font-size: 14px;
            }}
            .cta {{
                background: #007acc;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                display: inline-block;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🛠️ CloudFix</div>
                <div class="subtitle">Monthly Product Updates - {metadata.get('period', 'Recent Changes')}</div>
            </div>
            
            <div class="content">
                {changelog.replace('## ', '<h2>').replace('### ', '<h3>').replace('- ', '<li>').replace('\\n', '<br>')}
            </div>
            
            <div class="footer">
                <a href="https://cloudfix.com/features" class="cta">Explore New Features</a><br><br>
                <p>Questions about these updates? <a href="mailto:support@cloudfix.com">Contact our team</a></p>
                <p><small>You're receiving this because you're a CloudFix user. <a href="#">Manage preferences</a></small></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    plain_text = f"""
CloudFix Monthly Updates - {metadata.get('period', 'Recent Changes')}

{changelog}

---
Explore new features: https://cloudfix.com/features
Questions? Contact us: support@cloudfix.com

You're receiving this because you're a CloudFix user.
Manage preferences: [link]
    """.strip()
    
    return html_template, plain_text

def create_email_summary(changelog: str) -> str:
    """Create a concise 2-3 paragraph summary for email distribution."""
    lines = changelog.split('\n')
    
    # Extract key sections
    added_items = []
    fixed_items = []
    changed_items = []
    
    current_section = None
    for line in lines:
        line = line.strip()
        if line.startswith('### Added'):
            current_section = 'added'
        elif line.startswith('### Fixed'):
            current_section = 'fixed'
        elif line.startswith('### Changed'):
            current_section = 'changed'
        elif line.startswith('###'):
            current_section = None
        elif line.startswith('- ') and current_section:
            item = line[2:].strip()
            if current_section == 'added':
                added_items.append(item)
            elif current_section == 'fixed':
                fixed_items.append(item)
            elif current_section == 'changed':
                changed_items.append(item)
    
    # Create summary paragraphs
    summary_parts = []
    
    if added_items:
        summary_parts.append(f"This month we've introduced {len(added_items)} new features and improvements to make CloudFix even more powerful for AWS cost optimization. Key additions include {', '.join(added_items[:2])}{'...' if len(added_items) > 2 else ''}.")
    
    if fixed_items or changed_items:
        improvements_count = len(fixed_items) + len(changed_items)
        summary_parts.append(f"We've also made {improvements_count} enhancements and bug fixes based on your feedback, improving overall stability and performance.")
    
    summary_parts.append("These updates are automatically available in your CloudFix dashboard. Check out the full changelog below for complete details.")
    
    return ' '.join(summary_parts)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        config = AppConfig()
        dependencies = {
            "github_api": "configured" if config.github_token else "missing",
            "openai_api": "configured" if config.openai_api_key else "missing",
        }
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow(),
            dependencies=dependencies
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/generate-changelog", response_model=ChangelogResponse)
async def generate_changelog(request: ChangelogRequest):
    """Generate changelog for specified repository and date range."""
    try:
        logger.info(f"Generating changelog for {request.repository} ({request.start_date} to {request.end_date})")
        
        # Parse repository
        owner, repo = parse_repository_url(request.repository)
        
        # Fetch PRs for all specified branches
        all_prs = []
        repo_description = ""
        
        for branch in request.branches:
            try:
                prs, desc = fetch_prs_merged_between_dates_optimized(
                    owner, repo, request.start_date, request.end_date, branch
                )
                if prs is not None and not prs.empty:
                    prs['branch'] = branch
                    all_prs.append(prs)
                    if not repo_description:
                        repo_description = desc
            except Exception as e:
                logger.warning(f"Failed to fetch PRs from {branch}: {e}")
                continue
        
        if not all_prs:
            return ChangelogResponse(
                success=False,
                error="No PRs found in the specified date range and branches"
            )
        
        # Combine and deduplicate PRs
        import pandas as pd
        prs = pd.concat(all_prs, ignore_index=True)
        prs = prs.drop_duplicates(subset=['number'], keep='first')
        
        # Fetch commits
        commits = fetch_commits_from_prs_optimized(prs, owner, repo)
        
        if commits.empty:
            return ChangelogResponse(
                success=False,
                error="No commits found in the selected PRs"
            )
        
        # Extract messages
        messages = extract_messages_from_commits_optimized(commits)
        
        if not messages.strip():
            return ChangelogResponse(
                success=False,
                error="No valid commit messages found to generate changelog"
            )
        
        # Generate changelog
        changelog = gpt_inference_changelog_optimized(
            messages,
            request.start_date,
            request.end_date,
            owner,
            repo,
            repo_description,
            request.branches
        )
        
        if not changelog:
            return ChangelogResponse(
                success=False,
                error="Failed to generate changelog"
            )
        
        # Create metadata
        metadata = {
            "repository": f"{owner}/{repo}",
            "period": f"{request.start_date} to {request.end_date}",
            "branches": request.branches,
            "pr_count": len(prs),
            "commit_count": len(commits),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        response_data = {
            "success": True,
            "changelog": changelog,
            "metadata": metadata
        }
        
        # Format for email if requested
        if request.email_format:
            html_content, plain_text = format_for_email(changelog, metadata)
            summary = create_email_summary(changelog)
            
            response_data.update({
                "html_content": html_content,
                "plain_text": plain_text,
                "summary": summary
            })
        
        logger.info(f"Successfully generated changelog for {owner}/{repo}")
        return ChangelogResponse(**response_data)
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {e}")
        raise HTTPException(status_code=502, detail=f"GitHub API error: {str(e)}")
    except OpenAIAPIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/changelog/last-month")
async def get_last_month_changelog():
    """Convenience endpoint for monthly automation - generates changelog for last month."""
    today = date.today()
    first_day_this_month = today.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    
    request = ChangelogRequest(
        repository="trilogy-group/cloudfix-aws",
        start_date=first_day_last_month,
        end_date=last_day_last_month,
        branches=["production"],
        email_format=True
    )
    
    return await generate_changelog(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )