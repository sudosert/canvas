#!/usr/bin/env python3
"""
Reply to PR review comments on GitHub.

This script reads a pr_comments.txt file and creates replies to review comments.
It can reply to individual comments or create a general PR comment with all responses.

Usage:
    python reply_to_pr.py <pr_number> [options]

Examples:
    python reply_to_pr.py 42 --comments-file pr_comments.txt
    python reply_to_pr.py 42 --reply-all "All issues have been addressed"
    python reply_to_pr.py 42 --interactive
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
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


def make_github_request(url: str, method: str = 'GET', data: dict = None, token: Optional[str] = None) -> dict:
    """Make a request to the GitHub API."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'PR-Reply-Bot',
        'Content-Type': 'application/json'
    }
    
    if token:
        headers['Authorization'] = f'token {token}'
    
    request_data = None
    if data:
        request_data = json.dumps(data).encode('utf-8')
    
    request = urllib.request.Request(url, data=request_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        if e.code == 404:
            print(f"Error: Resource not found (404). Check the PR number and repository.")
        elif e.code == 401:
            print(f"Error: Unauthorized (401). Check your GitHub token.")
        elif e.code == 403:
            print(f"Error: Rate limited or forbidden (403). {error_body}")
        else:
            print(f"Error: HTTP {e.code} - {e.reason}")
            print(f"Response: {error_body}")
        sys.exit(1)
    except Exception as e:
        print(f"Error making request: {e}")
        sys.exit(1)


def parse_pr_comments(file_path: str) -> Dict:
    """Parse the pr_comments.txt file and extract review comments."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract PR info
    pr_match = re.search(r'\*\*PR:\*\* #(\d+)', content)
    pr_number = int(pr_match.group(1)) if pr_match else None
    
    # Extract review comments
    comments = []
    
    # Pattern for review comments with file/line info and comment ID
    review_pattern = r'={60}\nReview Comment by @([^\n]+) on ([^\n]+)\n={60}\n\*\*(\w+):\*\* ([^\n]+)\n\n(.+?)\n\n\[Comment ID: (\d+)\]\n\[File: ([^,]+), Line: (\d+)\]'

    for match in re.finditer(review_pattern, content, re.DOTALL):
        comments.append({
            'type': 'review_comment',
            'author': match.group(1),
            'date': match.group(2),
            'severity': match.group(3),
            'title': match.group(4),
            'body': match.group(5).strip(),
            'comment_id': int(match.group(6)),
            'file': match.group(7),
            'line': int(match.group(8))
        })
    
    # Pattern for general comments (without file/line)
    general_pattern = r'={60}\nComment by @([^\n]+) on ([^\n]+)\n={60}\n(.+?)(?=={60}|\Z)'
    
    for match in re.finditer(general_pattern, content, re.DOTALL):
        # Skip if it's a review comment (already captured)
        if 'Review Comment' in match.group(0):
            continue
        comments.append({
            'type': 'general_comment',
            'author': match.group(1),
            'date': match.group(2),
            'body': match.group(3).strip()
        })
    
    return {
        'pr_number': pr_number,
        'comments': comments
    }


def get_review_comments_from_api(repo: str, pr_number: int, token: str) -> List[dict]:
    """Fetch review comments from GitHub API to get comment IDs."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"
    return make_github_request(url, token=token)


def reply_to_review_comment(repo: str, pr_number: int, comment_id: int, body: str, token: str) -> dict:
    """
    Reply to a specific review comment using threaded replies.
    
    Uses the in_reply_to parameter to create a threaded conversation
    on the specific review comment.
    """
    # Extract owner and repo from the full repo string
    parts = repo.split('/')
    if len(parts) != 2:
        raise ValueError(f"Invalid repo format: {repo}. Expected 'owner/repo'")
    
    owner, repo_name = parts
    
    # Use the PR comments endpoint with in_reply_to for threading
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"
    
    # The in_reply_to field creates a threaded reply to the specified comment
    data = {
        'body': body,
        'in_reply_to': comment_id
    }
    
    return make_github_request(url, method='POST', data=data, token=token)


def create_pr_comment(repo: str, pr_number: int, body: str, token: str) -> dict:
    """Create a general comment on the PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    return make_github_request(url, method='POST', data={'body': body}, token=token)


def generate_reply_text(comment: dict, custom_message: str = None) -> str:
    """Generate a reply text for a comment."""
    if custom_message:
        return custom_message
    
    severity = comment.get('severity', '')
    title = comment.get('title', '')
    
    if severity == 'CRITICAL':
        return f"✅ **Fixed:** {title}\n\nThis critical issue has been addressed in the latest commit."
    elif severity == 'WARNING':
        return f"✅ **Fixed:** {title}\n\nThis warning has been addressed in the latest commit."
    else:
        return f"✅ **Addressed:** {title}\n\nThis has been fixed in the latest commit."


def main():
    parser = argparse.ArgumentParser(
        description='Reply to PR review comments on GitHub',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
    GITHUB_TOKEN or GH_TOKEN    GitHub personal access token (required)

Token Sources (in order of priority):
    1. --token command-line argument
    2. GITHUB_TOKEN environment variable
    3. GH_TOKEN environment variable
    4. .env file (GITHUB_TOKEN=xxx or GH_TOKEN=xxx)
    5. ~/.github_token file

Examples:
    # Reply to all comments with a generic message
    %(prog)s 42 --reply-all "All issues have been fixed in the latest commit"
    
    # Create a summary comment
    %(prog)s 42 --summary "All 6 review issues have been addressed"
    
    # Interactive mode - prompt for each comment
    %(prog)s 42 --interactive
    
    # Use custom comments file
    %(prog)s 42 --comments-file my_comments.txt --summary "Fixed"
        """
    )
    
    parser.add_argument(
        'pr_number',
        type=int,
        help='Pull request number to reply to'
    )
    
    parser.add_argument(
        '--repo',
        type=str,
        default=None,
        help='Repository in format "owner/repo" (default: auto-detect from git remote)'
    )
    
    parser.add_argument(
        '--comments-file',
        type=str,
        default='pr_comments.txt',
        help='Path to the pr_comments.txt file (default: pr_comments.txt)'
    )
    
    parser.add_argument(
        '--token', '-t',
        type=str,
        default=None,
        help='GitHub personal access token'
    )
    
    parser.add_argument(
        '--reply-all',
        type=str,
        metavar='MESSAGE',
        help='Reply to all review comments with the same message'
    )
    
    parser.add_argument(
        '--summary',
        type=str,
        metavar='MESSAGE',
        help='Create a general PR comment with a summary message'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive mode - prompt for reply to each comment'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be posted without actually posting'
    )
    
    args = parser.parse_args()
    
    # Get token
    token = args.token or get_github_token()
    if not token:
        print("Error: GitHub token is required. Set GITHUB_TOKEN environment variable or use --token")
        sys.exit(1)
    
    # Determine repository
    repo = args.repo
    if not repo:
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
        
        if 'github.com' in remote_url:
            parts = remote_url.replace('.git', '').split('github.com/')
            if len(parts) == 2:
                repo = parts[1]
        elif remote_url.startswith('git@github.com:'):
            repo = remote_url.replace('git@github.com:', '').replace('.git', '')
        
        if not repo:
            print("Error: Could not parse repository from remote URL.")
            sys.exit(1)
    
    # Parse comments file
    if not os.path.exists(args.comments_file):
        print(f"Error: Comments file not found: {args.comments_file}")
        sys.exit(1)
    
    parsed = parse_pr_comments(args.comments_file)
    comments = parsed['comments']
    
    if not comments:
        print("No comments found in the file.")
        sys.exit(0)
    
    print(f"Found {len(comments)} comments in {args.comments_file}")
    print(f"Repository: {repo}")
    print(f"PR: #{args.pr_number}")
    print()
    
    # Handle summary comment
    if args.summary:
        print(f"Creating summary comment...")
        if args.dry_run:
            print(f"[DRY RUN] Would post summary comment:")
            print(f"  {args.summary}")
        else:
            result = create_pr_comment(repo, args.pr_number, args.summary, token)
            print(f"✓ Summary comment created: {result.get('html_url')}")
        print()
    
    # Handle reply-all
    if args.reply_all:
        print(f"Replying to review comments with: '{args.reply_all}'")
        print("(Using threaded replies - each reply will appear under its parent comment)")
        for i, comment in enumerate(comments):
            if comment['type'] == 'review_comment':
                # Use the comment ID directly from the parsed file
                comment_id = comment.get('comment_id')
                file_path = comment['file']
                line = comment['line']

                if comment_id:
                    if args.dry_run:
                        print(f"[DRY RUN] Would reply to comment on {file_path}:{line} (threaded reply to comment ID: {comment_id})")
                    else:
                        try:
                            reply_to_review_comment(repo, args.pr_number, comment_id, args.reply_all, token)
                            print(f"✓ Replied to comment on {file_path}:{line} (threaded)")
                        except Exception as e:
                            print(f"✗ Failed to reply to comment on {file_path}:{line}: {e}")
                else:
                    print(f"⚠ No comment ID found for {file_path}:{line} - cannot reply")
        print()
    
    # Handle interactive mode
    if args.interactive:
        print("Interactive mode - reviewing each comment:")
        print("-" * 60)
        
        for i, comment in enumerate(comments):
            print(f"\nComment {i+1}/{len(comments)}:")
            print(f"Type: {comment['type']}")
            if comment['type'] == 'review_comment':
                print(f"File: {comment['file']}:{comment['line']}")
                print(f"Severity: {comment['severity']}")
                print(f"Issue: {comment['title']}")
            print(f"Body: {comment['body'][:200]}...")
            print()
            
            reply = input("Enter your reply (or 'skip' to skip, 'quit' to exit): ").strip()
            
            if reply.lower() == 'quit':
                print("Exiting...")
                break
            elif reply.lower() == 'skip':
                print("Skipped.")
                continue
            elif reply:
                if comment['type'] == 'review_comment':
                    # Use comment ID directly from parsed file for threading
                    comment_id = comment.get('comment_id')
                    file_path = comment['file']
                    line = comment['line']

                    if comment_id:
                        if args.dry_run:
                            print(f"[DRY RUN] Would reply to comment ID {comment_id} (threaded): {reply}")
                        else:
                            try:
                                reply_to_review_comment(repo, args.pr_number, comment_id, reply, token)
                                print(f"✓ Reply posted as threaded comment to ID {comment_id}.")
                            except Exception as e:
                                print(f"✗ Failed to post threaded reply: {e}")
                    else:
                        print(f"⚠ No comment ID found for {file_path}:{line} - cannot reply")
                else:
                    # Create a general comment
                    if args.dry_run:
                        print(f"[DRY RUN] Would post general comment: {reply}")
                    else:
                        create_pr_comment(repo, args.pr_number, reply, token)
                        print("✓ Comment posted.")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
