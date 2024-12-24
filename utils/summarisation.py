import os
from openai import OpenAI
import streamlit as st

def extract_messages_from_commits(pr_commit_data):
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

def gpt_inference_changelog(commits, start_date, end_date, owner, repo, repo_description, main_branch='main'):
    """Generates a changelog using GPT-4"""
    
    system_prompt = """Create a changelog from git commits following these rules:
    1. Group changes into sections: Added, Changed, Deprecated, Removed, Fixed, Security
    2. Keep entries clear and concise
    3. Include PR numbers as links [#123]
    4. Focus on user-facing changes. This summary will be made available to external end-users and customers
    5. Use active voice
    6. Start each entry with a verb (Added, Fixed, etc.)"""

    user_prompt = f"""Generate a changelog for {owner}/{repo} ({repo_description}) 
    Time period: {start_date} to {end_date}
    Branch: {main_branch}

    Commit messages:
    {commits}"""

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        changelog = response.choices[0].message.content
        
        return changelog
        
    except Exception as e:
        st.error(f"Error generating changelog: {str(e)}")
        return None