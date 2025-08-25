# CloudFix n8n Automation Setup Guide

This guide will help you set up automated monthly changelog generation and email distribution using n8n.

## 📋 Prerequisites

- n8n instance (cloud or self-hosted)
- CloudFix changelog generator deployed as API
- SMTP email service (SendGrid, Mailgun, or similar)
- CloudFix user mailing list
- GitHub API access
- OpenAI API access

## 🚀 Quick Setup

### Step 1: Deploy the API Wrapper

1. **Install dependencies:**
```bash
pip install flask python-dotenv
```

2. **Set environment variables:**
```bash
export GITHUB_API_KEY="your_github_token"
export OPENAI_API_KEY="your_openai_key"
export CHANGELOG_API_TOKEN="secure-random-token"
export PORT=5000
```

3. **Run the API:**
```bash
python automation/api_wrapper.py
```

4. **Test the API:**
```bash
curl -X POST http://localhost:5000/generate \
  -H "Authorization: Bearer secure-random-token" \
  -H "Content-Type: application/json" \
  -d '{
    "owner": "trilogy-group",
    "repo": "cloudfix-aws",
    "branches": ["production"],
    "days_back": 30,
    "format": "email"
  }'
```

### Step 2: Import n8n Workflow

1. **Open your n8n instance**
2. **Go to Workflows → Import from File**
3. **Upload:** `automation/n8n_workflow.json`
4. **Configure environment variables in n8n:**

### Step 3: Configure Environment Variables

Set these in your n8n environment:

| Variable | Description | Example |
|----------|-------------|---------|
| `CHANGELOG_API_URL` | Your API base URL | `https://api.yourserver.com` |
| `API_TOKEN` | API authentication token | `secure-random-token` |
| `CLOUDFIX_USERS_LIST` | Comma-separated email list | `user1@company.com,user2@company.com` |
| `ADMIN_EMAIL` | Admin notification email | `admin@cloudfix.com` |
| `UNSUBSCRIBE_URL` | Unsubscribe page URL | `https://cloudfix.com/unsubscribe` |
| `SLACK_WEBHOOK_URL` | Slack notifications (optional) | `https://hooks.slack.com/...` |

### Step 4: Configure SMTP Credentials

1. **In n8n, go to:** Settings → Credentials
2. **Add new credential:** Email (SMTP)
3. **Configure your email provider:**

**For SendGrid:**
```
Host: smtp.sendgrid.net
Port: 587
User: apikey
Password: your-sendgrid-api-key
```

**For Gmail:**
```
Host: smtp.gmail.com
Port: 587
User: your-email@gmail.com
Password: your-app-password
```

### Step 5: Test the Workflow

1. **Activate the workflow** in n8n
2. **Manual test:** Click "Execute Workflow"
3. **Check logs** for any errors
4. **Verify email delivery** to test accounts

## 🎯 Workflow Features

### ✅ **What It Does**

- **Runs monthly** (1st of each month at 1 PM EST)
- **Fetches data** from CloudFix repositories
- **Generates changelog** using AI
- **Sends beautiful emails** to user list
- **Handles errors gracefully** with fallback content
- **Notifies administrators** of issues
- **Tracks success** via Slack notifications

### 🔄 **Error Handling**

1. **Primary Path:** AI-generated changelog email
2. **Fallback Path:** Generic update email if generation fails
3. **Admin Alerts:** Immediate notification of failures
4. **Retry Logic:** Built-in retry for transient failures

### 📧 **Email Template Features**

- **Responsive design** for mobile and desktop
- **CloudFix branding** with gradient headers
- **Clean typography** and professional styling
- **Unsubscribe links** for compliance
- **Call-to-action buttons** linking to GitHub/dashboard

## 🛠 Advanced Configuration

### Customizing the Schedule

Change the cron expression in the "Monthly Trigger" node:

```json
{
  "cronExpression": "0 13 1 * *"  // 1st of month at 1 PM
}
```

**Common schedules:**
- `0 9 1 * *` - 1st of month at 9 AM
- `0 13 15 * *` - 15th of month at 1 PM  
- `0 10 * * 1` - Every Monday at 10 AM (weekly)

### Adding More Repositories

Edit the API wrapper's `ALLOWED_REPOS` list:

```python
ALLOWED_REPOS = [
    'trilogy-group/cloudfix-aws',
    'trilogy-group/cloudfix-frontend',
    'trilogy-group/cloudfix-api'
]
```

### Customizing Email Templates

The workflow includes HTML email templates. You can:

1. **Edit inline** in the n8n nodes
2. **Create external templates** and fetch via HTTP
3. **Use n8n's template system** for dynamic content

### User List Management

Currently uses environment variable. For dynamic lists:

1. **Database integration:** Query user database
2. **CRM integration:** Fetch from HubSpot/Salesforce
3. **CSV import:** Read from Google Sheets/Airtable

## 📊 Monitoring & Maintenance

### Health Checks

- **API health:** `GET /health` endpoint
- **n8n monitoring:** Built-in execution logs
- **Email delivery:** Provider webhooks/analytics

### Log Monitoring

Check logs for:
- API response times
- Email delivery failures
- GitHub API rate limits
- OpenAI API usage

### Monthly Review

1. **Verify email delivery** rates
2. **Review changelog quality** and user feedback
3. **Check API usage** and costs
4. **Update user lists** as needed

## 🚨 Troubleshooting

### Common Issues

**API Authentication Errors:**
```bash
# Check token configuration
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:5000/health
```

**Email Delivery Failures:**
- Verify SMTP credentials
- Check sender reputation
- Review email content for spam triggers

**GitHub Rate Limits:**
- Use personal access token with higher limits
- Implement request throttling
- Consider GitHub Apps for higher limits

**OpenAI API Errors:**
- Check API key validity
- Monitor usage quotas
- Implement fallback prompts

### Getting Help

1. **n8n Documentation:** https://docs.n8n.io/
2. **API Logs:** Check Flask application logs
3. **GitHub Issues:** Report bugs in the repository
4. **Community Forum:** n8n community for workflow help

## 🔄 Updates & Maintenance

### Updating the Workflow

1. **Export current workflow** as backup
2. **Import updated version**
3. **Test thoroughly** before activating
4. **Monitor first few executions**

### API Updates

1. **Deploy new API version**
2. **Update n8n environment variables** if needed
3. **Test workflow** with new API
4. **Monitor for compatibility issues**

This automation will provide reliable, monthly changelog emails to your CloudFix users with minimal maintenance required!