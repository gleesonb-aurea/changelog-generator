# test_github_api.py
import os
import requests
from datetime import datetime

def fetch_prs_merged_between_dates(owner, repo, start_date, end_date, main_branch='main'):
    """Fetches pull requests merged between start_date and end_date from a GitHub repository.

    Args:
        owner (str): GitHub username or organization name
        repo (str): Repository name
        start_date (str): Start date in ISO 8601 format (YYYY-MM-DD)
        end_date (str): End date in ISO 8601 format (YYYY-MM-DD)
        main_branch (str): The main branch name (default is 'main')

    Returns:
        list: Merged pull requests or None if request fails
    """
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise EnvironmentError("GITHUB_TOKEN environment variable not set")

    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    search_url = 'https://api.github.com/search/issues'
    query = f'repo:{owner}/{repo} is:pr is:merged base:{main_branch} merged:{start_date}..{end_date}'
    params = {
        'q': query,
        'sort': 'updated',
        'order': 'desc',
        'per_page': 100
    }

    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        prs = data.get('items', [])
        print(f"Total PRs fetched: {len(prs)}")
        return prs

    except requests.exceptions.RequestException as e:
        print(f"Error fetching PRs: {e}")
        return None

def main():
    # Configuration
    owner = 'trilogy-group'
    repo = 'cloudfix-aws'
    main_branch = 'production'
    start_date = '2024-10-01'
    end_date = '2024-11-30'

    prs = fetch_prs_merged_between_dates(owner, repo, start_date, end_date, main_branch)

    if prs:
        for pr in prs:
            print(f"PR #{pr['number']}: {pr['title']} | Merged At: {pr['closed_at']}")

if __name__ == "__main__":
    main()