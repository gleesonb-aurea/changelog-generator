import streamlit as st
import re
import pandas as pd
from datetime import datetime
from utils.github_data_fetch import (
    fetch_prs_merged_between_dates, 
    fetch_commits_from_prs,
)
from utils.summarisation import (
    gpt_inference_changelog, 
    extract_messages_from_commits,
)

st.title('Changelog Auto-Generator')
st.markdown("This app generates a CloudFix changelog based on merged Pull Requests.")

def validate_github_url(url):
    pattern = r'^https:\/\/github\.com\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)$'
    match = re.match(pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None, None

# Input fields
repository = st.text_input('Repository URL', 'https://github.com/trilogy-group/cloudfix-aws')
owner, repo = validate_github_url(repository)
if not owner or not repo:
    st.error('Invalid repository URL')
    st.stop()

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input('Start Date')
with col2:
    end_date = st.date_input('End Date')

available_branches = ['production', 'staging', 'qa']
selected_branches = st.multiselect(
    'Select branches to scan (default: production)',
    available_branches,
    default=['production']
)

if not selected_branches:
    st.error('Please select at least one branch')
    st.stop()

st.markdown("---")
st.markdown(f"**Repository**: {owner}/{repo}")
st.markdown(f"**Date Range**: {start_date} to {end_date}")
st.markdown(f"**Selected Branches**: {', '.join(selected_branches)}")

if st.button('Generate Changelog'):
    all_prs = []
    repo_description = None
    
    with st.spinner('Fetching PRs...'):
        for branch in selected_branches:
            branch_prs, repo_description = fetch_prs_merged_between_dates(owner, repo, start_date, end_date, branch)
            if branch_prs is not None and not branch_prs.empty:
                # Add branch information to the PRs
                branch_prs['branch'] = branch
                all_prs.append(branch_prs)
        
        if not all_prs:
            st.error("Failed to fetch PRs or no PRs found")
            st.stop()
            
        # Combine all PRs into a single DataFrame
        prs = pd.concat(all_prs, ignore_index=True)
        st.success(f"Found {len(prs)} PRs across {len(selected_branches)} branches")
    
    with st.spinner('Fetching commits...'):
        commits = fetch_commits_from_prs(prs, owner, repo)
        st.success(f"Found {len(commits)} commits")
        
        with st.spinner('Generating changelog...'):
            messages = extract_messages_from_commits(commits)
            changelog = gpt_inference_changelog(
                messages, 
                start_date, 
                end_date,
                owner, 
                repo, 
                repo_description, 
                selected_branches
            )
            
            st.markdown("## Generated Changelog")
            st.markdown(changelog)
            
            # Display raw PR data in an expander
            with st.expander("View Raw PR Data"):
                st.dataframe(prs[['title', 'number', 'merged_at', 'branch']])


def image(src_as_string, **style):
    return img(src=src_as_string, style=styles(**style))

def link(hyperlink, text, **style):
    return a(_href=hyperlink, _target="_blank", style=styles(**style))(text)


def layout(*args):
    style = """
    <style>
      # MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
     .stApp { bottom: 105px; }
    </style>
    """

    style_div = styles(
        position="fixed",
        left=0,
        bottom=0,
        margin=px(0, 0, 0, 0),
        width=percent(100),
        color="black",
        text_align="center",
        height="auto",
        opacity=1
    )

    style_hr = styles(
        display="block",
        margin=px(8, 8, "auto", "auto"),
        border_style="inset",
        border_width=px(2)
    )

    body = p()
    foot = div(
        style=style_div
    )(
        hr(
            style=style_hr
        ),
        body
    )

    st.markdown(style, unsafe_allow_html=True)

    for arg in args:
        if isinstance(arg, str):
            body(arg)

        elif isinstance(arg, HtmlElement):
            body(arg)

    st.markdown(str(foot), unsafe_allow_html=True)

if __name__ == "__main__":
    pass 