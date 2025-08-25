"""
Email template system for CloudFix changelog distribution.
Provides responsive HTML and plain text templates optimized for various email clients.
"""

from typing import Dict, Any, Tuple
from datetime import datetime, date
import re

class EmailTemplateEngine:
    """Email template engine for CloudFix changelog distribution."""
    
    def __init__(self):
        self.brand_colors = {
            'primary': '#007acc',
            'secondary': '#004d7a',
            'accent': '#00b4d8',
            'text': '#333333',
            'text_light': '#666666',
            'background': '#f9f9f9',
            'white': '#ffffff'
        }
        
        self.base_styles = """
        <style>
            /* Reset and base styles */
            body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
            table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
            img { -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }
            
            /* Main styles */
            body {
                margin: 0 !important;
                padding: 0 !important;
                background-color: #f9f9f9;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
            }
            
            .email-container {
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
            }
            
            .header {
                background: linear-gradient(135deg, #007acc 0%, #004d7a 100%);
                padding: 30px 20px;
                text-align: center;
            }
            
            .logo {
                font-size: 28px;
                font-weight: bold;
                color: #ffffff;
                margin: 0;
                text-decoration: none;
            }
            
            .subtitle {
                color: #ffffff;
                font-size: 16px;
                margin: 10px 0 0 0;
                opacity: 0.9;
            }
            
            .content {
                padding: 30px 20px;
            }
            
            .summary {
                background: #f8f9fa;
                border-left: 4px solid #007acc;
                padding: 20px;
                margin: 0 0 30px 0;
                font-size: 16px;
                line-height: 1.6;
            }
            
            h2 {
                color: #007acc;
                font-size: 22px;
                margin: 30px 0 15px 0;
                border-bottom: 2px solid #007acc;
                padding-bottom: 10px;
            }
            
            h3 {
                color: #333333;
                font-size: 18px;
                margin: 25px 0 12px 0;
                font-weight: 600;
            }
            
            .changelog-section {
                margin-bottom: 25px;
            }
            
            .change-item {
                background: #f8f9fa;
                border-left: 3px solid #007acc;
                padding: 12px 15px;
                margin: 8px 0;
                border-radius: 4px;
                font-size: 14px;
            }
            
            .change-item.added { border-left-color: #28a745; }
            .change-item.fixed { border-left-color: #dc3545; }
            .change-item.changed { border-left-color: #ffc107; }
            .change-item.security { border-left-color: #6f42c1; }
            
            .cta-section {
                text-align: center;
                margin: 40px 0;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 8px;
            }
            
            .cta-button {
                display: inline-block;
                background: #007acc;
                color: #ffffff !important;
                padding: 14px 28px;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                margin: 10px;
                transition: background-color 0.3s;
            }
            
            .cta-button:hover {
                background: #004d7a;
            }
            
            .stats-grid {
                display: table;
                width: 100%;
                margin: 20px 0;
            }
            
            .stat-item {
                display: table-cell;
                text-align: center;
                padding: 15px;
                border-right: 1px solid #eee;
            }
            
            .stat-item:last-child { border-right: none; }
            
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                color: #007acc;
                display: block;
            }
            
            .stat-label {
                font-size: 12px;
                color: #666666;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .footer {
                background: #333333;
                color: #ffffff;
                padding: 30px 20px;
                text-align: center;
            }
            
            .footer a {
                color: #007acc;
                text-decoration: none;
            }
            
            .footer-links {
                margin: 20px 0;
            }
            
            .footer-links a {
                color: #ffffff;
                text-decoration: none;
                margin: 0 15px;
                font-size: 14px;
            }
            
            .social-links {
                margin: 20px 0;
            }
            
            .social-links a {
                display: inline-block;
                margin: 0 10px;
                color: #ffffff;
                font-size: 18px;
            }
            
            .unsubscribe {
                font-size: 12px;
                color: #999999;
                margin-top: 20px;
            }
            
            /* Mobile responsive */
            @media screen and (max-width: 600px) {
                .email-container { width: 100% !important; }
                .content { padding: 20px 15px !important; }
                .header { padding: 20px 15px !important; }
                .logo { font-size: 24px !important; }
                .stats-grid { display: block !important; }
                .stat-item { display: block !important; border-right: none !important; border-bottom: 1px solid #eee; }
                .stat-item:last-child { border-bottom: none; }
                .cta-button { display: block !important; margin: 10px 0 !important; }
            }
            
            /* Dark mode support */
            @media (prefers-color-scheme: dark) {
                .email-container { background-color: #1a1a1a !important; }
                .content { background-color: #1a1a1a !important; color: #ffffff !important; }
                .summary { background-color: #2a2a2a !important; color: #ffffff !important; }
                .change-item { background-color: #2a2a2a !important; color: #ffffff !important; }
                .cta-section { background-color: #2a2a2a !important; }
                h2, h3 { color: #ffffff !important; }
            }
        </style>
        """
    
    def generate_html_template(
        self,
        changelog: str,
        summary: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Generate complete HTML email template."""
        
        # Parse changelog sections
        sections = self._parse_changelog_sections(changelog)
        
        # Generate stats
        stats = self._generate_stats(metadata)
        
        # Create month/year for title
        period = metadata.get('period', 'Recent Updates')
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta name="x-apple-disable-message-reformatting">
            <title>CloudFix Product Updates - {period}</title>
            {self.base_styles}
        </head>
        <body>
            <div class="email-container">
                
                <!-- Header -->
                <div class="header">
                    <h1 class="logo">🛠️ CloudFix</h1>
                    <p class="subtitle">Product Updates - {period}</p>
                </div>
                
                <!-- Main Content -->
                <div class="content">
                    
                    <!-- Summary -->
                    <div class="summary">
                        <strong>What's New This Month</strong><br>
                        {summary}
                    </div>
                    
                    <!-- Stats -->
                    <div class="stats-grid">
                        {stats}
                    </div>
                    
                    <!-- Changelog Sections -->
                    {sections}
                    
                    <!-- Call to Action -->
                    <div class="cta-section">
                        <h3>Ready to explore these new features?</h3>
                        <a href="https://cloudfix.com/dashboard" class="cta-button">Open Dashboard</a>
                        <a href="https://cloudfix.com/features" class="cta-button">View All Features</a>
                    </div>
                    
                </div>
                
                <!-- Footer -->
                <div class="footer">
                    <div class="footer-links">
                        <a href="https://cloudfix.com/features">Features</a>
                        <a href="https://cloudfix.com/pricing">Pricing</a>
                        <a href="https://cloudfix.com/support">Support</a>
                        <a href="https://cloudfix.com/blog">Blog</a>
                    </div>
                    
                    <div class="social-links">
                        <a href="https://twitter.com/cloudfix">🐦</a>
                        <a href="https://linkedin.com/company/cloudfix">💼</a>
                        <a href="https://github.com/cloudfix">👨‍💻</a>
                    </div>
                    
                    <p>Questions about these updates? <a href="mailto:support@cloudfix.com">Contact our team</a></p>
                    
                    <div class="unsubscribe">
                        <p>You're receiving this because you're a CloudFix user.</p>
                        <p><a href="{{unsubscribe_url}}">Manage preferences</a> | <a href="{{unsubscribe_url}}">Unsubscribe</a></p>
                    </div>
                </div>
                
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def generate_plain_text_template(
        self,
        changelog: str,
        summary: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Generate plain text email template."""
        
        period = metadata.get('period', 'Recent Updates')
        repository = metadata.get('repository', 'CloudFix')
        
        # Clean markdown formatting for plain text
        plain_changelog = self._markdown_to_plain_text(changelog)
        
        template = f"""
CloudFix Product Updates - {period}

{summary}

WHAT'S NEW:
{plain_changelog}

QUICK LINKS:
- Dashboard: https://cloudfix.com/dashboard
- New Features: https://cloudfix.com/features
- Support: https://cloudfix.com/support

Need help with any of these updates? Reply to this email or contact us at support@cloudfix.com.

---
CloudFix - AWS Cost Optimization Made Simple
https://cloudfix.com

You're receiving this because you're a CloudFix user.
Manage preferences: {{unsubscribe_url}}
        """.strip()
        
        return template
    
    def generate_newsletter_template(
        self,
        changelog: str,
        summary: str,
        metadata: Dict[str, Any],
        additional_content: Dict[str, str] = None
    ) -> str:
        """Generate newsletter-style template with additional sections."""
        
        additional_content = additional_content or {}
        
        # Base template with newsletter sections
        newsletter_sections = ""
        
        # Add blog/content section if provided
        if additional_content.get('featured_blog'):
            newsletter_sections += f"""
            <div class="newsletter-section">
                <h3>📝 From the Blog</h3>
                <div class="blog-preview">
                    {additional_content['featured_blog']}
                    <a href="{additional_content.get('blog_url', '#')}" class="read-more">Read More →</a>
                </div>
            </div>
            """
        
        # Add community section if provided
        if additional_content.get('community_highlight'):
            newsletter_sections += f"""
            <div class="newsletter-section">
                <h3>👥 Community Highlight</h3>
                <div class="community-preview">
                    {additional_content['community_highlight']}
                </div>
            </div>
            """
        
        # Insert newsletter sections before CTA
        base_template = self.generate_html_template(changelog, summary, metadata)
        
        # Insert newsletter sections before CTA
        cta_section = '<div class="cta-section">'
        newsletter_template = base_template.replace(
            cta_section,
            f"{newsletter_sections}{cta_section}"
        )
        
        return newsletter_template
    
    def _parse_changelog_sections(self, changelog: str) -> str:
        """Parse changelog into styled HTML sections."""
        sections_html = ""
        lines = changelog.split('\n')
        current_section = ""
        current_items = []
        
        section_classes = {
            'Added': 'added',
            'Fixed': 'fixed',
            'Changed': 'changed',
            'Security': 'security',
            'Removed': 'removed',
            'Deprecated': 'deprecated'
        }
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('### '):
                # Save previous section
                if current_section and current_items:
                    css_class = section_classes.get(current_section, '')
                    items_html = ''.join([f'<div class="change-item {css_class}">{item}</div>' for item in current_items])
                    sections_html += f"""
                    <div class="changelog-section">
                        <h3>{current_section}</h3>
                        {items_html}
                    </div>
                    """
                
                # Start new section
                current_section = line.replace('### ', '')
                current_items = []
                
            elif line.startswith('- ') and current_section:
                item = line[2:].strip()
                # Convert [#123] links to proper HTML links
                item = re.sub(r'\[#(\d+)\]', r'<a href="https://github.com/trilogy-group/cloudfix-aws/pull/\1">[#\1]</a>', item)
                current_items.append(item)
        
        # Don't forget the last section
        if current_section and current_items:
            css_class = section_classes.get(current_section, '')
            items_html = ''.join([f'<div class="change-item {css_class}">{item}</div>' for item in current_items])
            sections_html += f"""
            <div class="changelog-section">
                <h3>{current_section}</h3>
                {items_html}
            </div>
            """
        
        return sections_html
    
    def _generate_stats(self, metadata: Dict[str, Any]) -> str:
        """Generate statistics section HTML."""
        stats = []
        
        if metadata.get('pr_count'):
            stats.append(f'<div class="stat-item"><span class="stat-number">{metadata["pr_count"]}</span><span class="stat-label">Pull Requests</span></div>')
        
        if metadata.get('commit_count'):
            stats.append(f'<div class="stat-item"><span class="stat-number">{metadata["commit_count"]}</span><span class="stat-label">Commits</span></div>')
        
        # Add branches count
        branches = metadata.get('branches', [])
        if branches:
            stats.append(f'<div class="stat-item"><span class="stat-number">{len(branches)}</span><span class="stat-label">Branches</span></div>')
        
        # Add time period
        period = metadata.get('period', '')
        if period:
            days = len(period.split(' to ')) # Simple approximation
            stats.append(f'<div class="stat-item"><span class="stat-number">{days * 15}</span><span class="stat-label">Days Period</span></div>')
        
        return ''.join(stats)
    
    def _markdown_to_plain_text(self, markdown: str) -> str:
        """Convert markdown changelog to plain text."""
        # Remove markdown formatting
        text = re.sub(r'### (.+)', r'\n\1:\n', markdown)
        text = re.sub(r'## (.+)', r'\n\1\n' + '='*20, text)
        text = re.sub(r'- (.+)', r'  • \1', text)
        text = re.sub(r'\[#(\d+)\]', r'[PR #\1]', text)
        
        return text.strip()

# Template usage examples and factory functions
def create_standard_email(changelog: str, summary: str, metadata: Dict[str, Any]) -> Tuple[str, str]:
    """Create standard CloudFix email templates."""
    engine = EmailTemplateEngine()
    
    html = engine.generate_html_template(changelog, summary, metadata)
    text = engine.generate_plain_text_template(changelog, summary, metadata)
    
    return html, text

def create_newsletter_email(
    changelog: str, 
    summary: str, 
    metadata: Dict[str, Any],
    featured_blog: str = None,
    community_highlight: str = None
) -> Tuple[str, str]:
    """Create newsletter-style email templates with additional content."""
    engine = EmailTemplateEngine()
    
    additional_content = {}
    if featured_blog:
        additional_content['featured_blog'] = featured_blog
    if community_highlight:
        additional_content['community_highlight'] = community_highlight
    
    html = engine.generate_newsletter_template(changelog, summary, metadata, additional_content)
    text = engine.generate_plain_text_template(changelog, summary, metadata)
    
    return html, text

# Test template generation
if __name__ == "__main__":
    # Example usage
    test_changelog = """
## CloudFix Updates - January 2024

### Added
- New cost optimization recommendations for RDS instances [#123]
- Enhanced dashboard with real-time savings tracking [#124]
- Integration with AWS Config for compliance monitoring [#125]

### Fixed
- Resolved issue with S3 bucket analysis timing out [#126]
- Fixed dashboard loading performance on large accounts [#127]

### Changed
- Updated UI for better mobile experience [#128]
- Improved email notification formatting [#129]
    """
    
    test_summary = "This month we've introduced 3 new features and improvements to make CloudFix even more powerful for AWS cost optimization. Key additions include enhanced RDS recommendations and real-time savings tracking."
    
    test_metadata = {
        'repository': 'trilogy-group/cloudfix-aws',
        'period': 'January 1, 2024 to January 31, 2024',
        'branches': ['production'],
        'pr_count': 7,
        'commit_count': 23,
        'generated_at': datetime.now().isoformat()
    }
    
    html, text = create_standard_email(test_changelog, test_summary, test_metadata)
    
    # Save test templates
    with open('/tmp/test_email.html', 'w') as f:
        f.write(html)
    
    with open('/tmp/test_email.txt', 'w') as f:
        f.write(text)
    
    print("Test templates generated: /tmp/test_email.html and /tmp/test_email.txt")