#!/usr/bin/env python3
"""
Fetch pull request comments from a GitHub repository.

This script retrieves PR comments, review comments, and issue comments
from a specified pull request and saves them to a file for use as prompts.

Usage:
    python fetch_pr_comments.py <pr_number> [options]
    
Examples:
    python fetch_pr_comments.py 42
    python fetch_pr_comments.py 42 --repo owner/repo --output comments.txt
    python fetch_pr_comments.py 42 --token YOUR_GITHUB_TOKEN
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import urllib.request
import urllib.error


def get_github_token() -> Optional[str]:
    """Get GitHub token from environment variable or .env file."""
    # Check environment variables first
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        return token
    
    # Try to load from .env file in project root
    env_paths = [
        '.env',
        '.env.local',
        '.env.github',
        os.path.expanduser('~/.github_token'),
        os.path.expanduser('~/.config/github/token'),
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('GITHUB_TOKEN='):
                            return line.split('=', 1)[1].strip().strip('"\'')
                        if line.startswith('GH_TOKEN='):
                            return line.split('=', 1)[1].strip().strip('"\'')
            except Exception:
                continue
    
    return None


def make_github_request(url: str, token: Optional[str] = None) -> dict:
    """Make a request to the GitHub API."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'PR-Comments-Fetcher'
    }
    
    if token:
        headers['Authorization'] = f'token {token}'
    
    request = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: Resource not found (404). Check the PR number and repository.")
        elif e.code == 401:
            print(f"Error: Unauthorized (401). Check your GitHub token.")
        elif e.code == 403:
            print(f"Error: Rate limited (403). Try providing a GitHub token.")
        else:
            print(f"Error: HTTP {e.code} - {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"Error making request: {e}")
        sys.exit(1)


def fetch_pr_details(repo: str, pr_number: int, token: Optional[str] = None) -> dict:
    """Fetch pull request details."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    return make_github_request(url, token)


def fetch_pr_comments(repo: str, pr_number: int, token: Optional[str] = None) -> List[dict]:
    """Fetch PR comments (issue comments)."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    return make_github_request(url, token)


def fetch_review_comments(repo: str, pr_number: int, token: Optional[str] = None) -> List[dict]:
    """Fetch review comments (line-specific comments)."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"
    return make_github_request(url, token)


def fetch_reviews(repo: str, pr_number: int, token: Optional[str] = None) -> List[dict]:
    """Fetch PR reviews."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    return make_github_request(url, token)


def format_comment(comment: dict, comment_type: str = "Comment") -> str:
    """Format a single comment for output."""
    author = comment.get('user', {}).get('login', 'Unknown')
    body = comment.get('body', '').strip()
    created_at = comment.get('created_at', '')
    comment_id = comment.get('id', '')

    # Parse and format date
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d %H:%M UTC')
        except:
            date_str = created_at
    else:
        date_str = 'Unknown date'

    # Format the comment
    output = f"""
{'='*60}
{comment_type} by @{author} on {date_str}
{'='*60}
{body}
"""

    # Add comment ID for reply purposes
    if comment_id:
        output += f"\n[Comment ID: {comment_id}]"

    # Add line information for review comments
    if 'path' in comment:
        path = comment.get('path', '')
        line = comment.get('line', '')
        if line:
            output += f"\n[File: {path}, Line: {line}]"
        else:
            output += f"\n[File: {path}]"

    return output


def format_review(review: dict) -> str:
    """Format a review for output."""
    author = review.get('user', {}).get('login', 'Unknown')
    state = review.get('state', 'COMMENTED')
    body = review.get('body', '').strip()
    created_at = review.get('submitted_at', '')
    
    # Parse and format date
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d %H:%M UTC')
        except:
            date_str = created_at
    else:
        date_str = 'Unknown date'
    
    # Only include reviews with body text
    if not body:
        return ""
    
    return f"""
{'='*60}
Review by @{author} ({state}) on {date_str}
{'='*60}
{body}
"""


def generate_prompt_output(
    pr_details: dict,
    pr_comments: List[dict],
    review_comments: List[dict],
    reviews: List[dict]
) -> str:
    """Generate the formatted output for use as a prompt."""

    pr_title = pr_details.get('title', 'Unknown Title')
    pr_body = (pr_details.get('body') or '').strip()
    pr_author = pr_details.get('user', {}).get('login', 'Unknown')
    pr_url = pr_details.get('html_url', '')
    pr_number = pr_details.get('number', '')

    output = f"""# Pull Request Comments

**PR:** #{pr_number} - {pr_title}
**Author:** @{pr_author}
**URL:** {pr_url}

---

## PR Description

{pr_body if pr_body else '*No description provided*'}

---

## Comments and Reviews

"""
    
    # Add PR comments (issue comments)
    if pr_comments:
        output += "### General Comments\n\n"
        for comment in pr_comments:
            output += format_comment(comment, "Comment")
            output += "\n"
    
    # Add reviews
    review_count = 0
    for review in reviews:
        formatted = format_review(review)
        if formatted:
            if review_count == 0:
                output += "### Reviews\n\n"
            output += formatted
            output += "\n"
            review_count += 1
    
    # Add review comments (line-specific)
    if review_comments:
        output += "### Code Review Comments\n\n"
        for comment in review_comments:
            output += format_comment(comment, "Review Comment")
            output += "\n"
    
    # Summary
    total_comments = len(pr_comments) + len(review_comments) + review_count
    output += f"""
---

## Summary

- **Total Comments:** {total_comments}
- **General Comments:** {len(pr_comments)}
- **Reviews:** {review_count}
- **Code Review Comments:** {len(review_comments)}

---

*Generated for use as AI prompt context*
"""
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Fetch pull request comments from GitHub for use as prompts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
    GITHUB_TOKEN or GH_TOKEN    GitHub personal access token (optional but recommended)

Token Sources (in order of priority):
    1. --token command-line argument
    2. GITHUB_TOKEN environment variable
    3. GH_TOKEN environment variable
    4. .env file (GITHUB_TOKEN=xxx or GH_TOKEN=xxx)
    5. .env.local file
    6. .env.github file
    7. ~/.github_token file
    8. ~/.config/github/token file

Examples:
    %(prog)s 42
    %(prog)s 42 --repo owner/repo --output pr_comments.txt
    %(prog)s 42 --token YOUR_TOKEN --include-reviews
    
    # Using .env file
    echo "GITHUB_TOKEN=ghp_xxxxxxxx" > .env
    %(prog)s 42
        """
    )
    
    parser.add_argument(
        'pr_number',
        type=int,
        help='Pull request number to fetch comments from'
    )
    
    parser.add_argument(
        '--repo',
        type=str,
        default=None,
        help='Repository in format "owner/repo" (default: auto-detect from git remote)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='pr_comments.txt',
        help='Output file path (default: pr_comments.txt)'
    )
    
    parser.add_argument(
        '--token', '-t',
        type=str,
        default=None,
        help='GitHub personal access token (or set GITHUB_TOKEN env var)'
    )
    
    parser.add_argument(
        '--include-reviews',
        action='store_true',
        help='Include PR reviews in addition to comments'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output raw JSON instead of formatted text'
    )
    
    args = parser.parse_args()
    
    # Determine repository
    repo = args.repo
    if not repo:
        # Try to detect from git remote
        import subprocess
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'upstream'],
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
        except:
            try:
                result = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                remote_url = result.stdout.strip()
            except:
                print("Error: Could not detect repository from git remote.")
                print("Please specify --repo owner/repo")
                sys.exit(1)
        
        # Parse owner/repo from URL
        if 'github.com' in remote_url:
            parts = remote_url.replace('.git', '').split('github.com/')
            if len(parts) == 2:
                repo = parts[1]
        elif remote_url.startswith('git@github.com:'):
            repo = remote_url.replace('git@github.com:', '').replace('.git', '')
        
        if not repo:
            print("Error: Could not parse repository from remote URL.")
            print("Please specify --repo owner/repo")
            sys.exit(1)
    
    print(f"Fetching PR #{args.pr_number} from {repo}...")
    
    # Get token
    token = args.token or get_github_token()
    if not token:
        print("Warning: No GitHub token provided. Rate limits may apply.")
        print("Set GITHUB_TOKEN environment variable, use --token, or create a .env file:")
        print("  echo 'GITHUB_TOKEN=ghp_xxxxxxxx' > .env")
    
    # Fetch data
    try:
        pr_details = fetch_pr_details(repo, args.pr_number, token)
        print(f"✓ PR: {pr_details.get('title')}")
        
        pr_comments = fetch_pr_comments(repo, args.pr_number, token)
        print(f"✓ Found {len(pr_comments)} general comments")
        
        review_comments = fetch_review_comments(repo, args.pr_number, token)
        print(f"✓ Found {len(review_comments)} code review comments")
        
        reviews = []
        if args.include_reviews:
            reviews = fetch_reviews(repo, args.pr_number, token)
            print(f"✓ Found {len(reviews)} reviews")
        
    except Exception as e:
        print(f"Error fetching PR data: {e}")
        sys.exit(1)
    
    # Generate output
    if args.json:
        output_data = {
            'pr_details': pr_details,
            'pr_comments': pr_comments,
            'review_comments': review_comments,
            'reviews': reviews
        }
        output = json.dumps(output_data, indent=2)
    else:
        output = generate_prompt_output(pr_details, pr_comments, review_comments, reviews)
    
    # Write to file
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"\n✓ Comments saved to: {args.output}")
    print(f"  Total items: {len(pr_comments) + len(review_comments) + len(reviews)}")


if __name__ == '__main__':
    main()
