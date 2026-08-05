"""
Native GitHub Integration for JARVIS using GitHub CLI (gh) directly.
"""
import subprocess
import json
import os
from pathlib import Path
from datetime import datetime


class GitHubTool:
    """Native GitHub Tool using gh CLI directly"""
    
    def __init__(self, default_repo: str = "nivedjkr/jarvis-assistant"):
        self.default_repo = default_repo
        self.watch_repos = [default_repo]
        self.check_interval_minutes = 30
        self._load_config()

    def verify_gh_auth(self) -> bool:
        try:
            result = subprocess.run(
                ['gh', 'auth', 'status'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def _load_config(self):
        try:
            import yaml
            if Path('config.yaml').exists():
                with open('config.yaml', 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                gh_cfg = config.get('github', {})
                self.default_repo = gh_cfg.get('default_repo', self.default_repo)
                self.watch_repos = gh_cfg.get('watch_repos', [self.default_repo])
                self.check_interval_minutes = gh_cfg.get('check_interval_minutes', 30)
        except Exception:
            pass

    def _gh(self, *args, as_json=True) -> dict | list | str:
        cmd = ['gh'] + list(args)
        if as_json:
            cmd += ['--json', self._json_fields(args)]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode != 0:
                return {'error': result.stderr.strip() or result.stdout.strip()}
            if as_json:
                return json.loads(result.stdout)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return {'error': 'GitHub request timed out'}
        except Exception as e:
            return {'error': str(e)}

    def _json_fields(self, args) -> str:
        cmd = args[0] if args else ''
        fields = {
            'issue': 'number,title,state,createdAt,author',
            'pr': 'number,title,state,createdAt,author,url',
            'run': 'name,status,conclusion,createdAt,url',
            'repo': 'name,description,stargazerCount,forks,url'
        }
        return fields.get(cmd, 'name,url')

    # === ISSUES ===
    def list_issues(self, repo=None, state='open', limit=10) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'issue', 'list', '--state', state, '--limit', str(limit), '--json', 'number,title,state,createdAt,author']
        if target_repo:
            cmd.extend(['--repo', target_repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() or result.stdout.strip()}"
            issues = json.loads(result.stdout)
            if not issues:
                return f"No {state} issues in {target_repo}, sir."
            lines = [f"#{i['number']} {i['title']}" for i in issues]
            return f"{len(issues)} {state} issues in {target_repo}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing issues: {str(e)}"

    def create_issue(self, title: str, body: str = '', repo=None) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'issue', 'create', '--title', title]
        if target_repo:
            cmd.extend(['--repo', target_repo])
        if body:
            cmd.extend(['--body', body])
        else:
            cmd.extend(['--body', ''])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Failed to create issue: {result.stderr.strip() or result.stdout.strip()}"
            return f"Issue created, sir: {result.stdout.strip()}"
        except Exception as e:
            return f"Error creating issue: {str(e)}"

    def close_issue(self, number: int, repo=None) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'issue', 'close', str(number)]
        if target_repo:
            cmd.extend(['--repo', target_repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Failed: {result.stderr.strip() or result.stdout.strip()}"
            return f"Issue #{number} closed, sir."
        except Exception as e:
            return f"Error closing issue: {str(e)}"

    # === PULL REQUESTS ===
    def list_prs(self, repo=None, state='open', limit=10) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'pr', 'list', '--state', state, '--limit', str(limit), '--json', 'number,title,state,author,url']
        if target_repo:
            cmd.extend(['--repo', target_repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() or result.stdout.strip()}"
            prs = json.loads(result.stdout)
            if not prs:
                return f"No {state} PRs in {target_repo}, sir."
            lines = [f"#{p['number']} {p['title']}" for p in prs]
            return f"{len(prs)} {state} PRs:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing PRs: {str(e)}"

    def view_pr(self, number: int, repo=None) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'pr', 'view', str(number), '--json', 'number,title,state,body,author,url']
        if target_repo:
            cmd.extend(['--repo', target_repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() or result.stdout.strip()}"
            pr = json.loads(result.stdout)
            return (f"PR #{pr['number']}: {pr['title']}\n"
                    f"State: {pr['state']}\n"
                    f"Author: {pr.get('author', {}).get('login', 'unknown')}\n"
                    f"URL: {pr['url']}")
        except Exception as e:
            return f"Error viewing PR: {str(e)}"

    # === CI / ACTIONS ===
    def ci_status(self, repo=None, limit=5) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'run', 'list', '--limit', str(limit), '--json', 'name,status,conclusion,createdAt,url']
        if target_repo:
            cmd.extend(['--repo', target_repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() or result.stdout.strip()}"
            runs = json.loads(result.stdout)
            if not runs:
                return "No recent CI runs, sir."
            latest = runs[0]
            conclusion = latest.get('conclusion', 'in_progress') or 'in_progress'
            status_emoji = '✓' if conclusion == 'success' else '✗'
            return (f"Latest CI: {status_emoji} {conclusion.upper()}\n"
                    f"Workflow: {latest['name']}\n"
                    f"URL: {latest['url']}")
        except Exception as e:
            return f"Error checking CI status: {str(e)}"

    def ci_logs(self, run_id: str, repo=None) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'run', 'view', str(run_id), '--log-failed']
        if target_repo:
            cmd.extend(['--repo', target_repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.stdout.strip():
                return result.stdout.strip()[:2000]
            return "No failed logs found."
        except Exception as e:
            return f"Error fetching CI logs: {str(e)}"

    # === REPO INFO ===
    def repo_info(self, repo=None) -> str:
        target_repo = repo or self.default_repo
        cmd = ['gh', 'repo', 'view', target_repo, '--json', 'name,description,stargazerCount,forkCount,url']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() or result.stdout.strip()}"
            r = json.loads(result.stdout)
            return (f"{r['name']}: {r.get('description', '')}\n"
                    f"Stars: {r.get('stargazerCount', 0)} | "
                    f"Forks: {r.get('forkCount', 0)}\n"
                    f"URL: {r['url']}")
        except Exception as e:
            return f"Error getting repo info: {str(e)}"

    def list_repos(self, limit=50, **kwargs) -> str:
        try:
            lim = int(limit) if (limit is not None and str(limit).isdigit()) else 50
        except Exception:
            lim = 50
        cmd = ['gh', 'repo', 'list', '--limit', str(lim), '--json', 'name,nameWithOwner,description,url,isPrivate,primaryLanguage']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error listing repos: {result.stderr.strip() or result.stdout.strip()}"
            repos = json.loads(result.stdout)
            if not repos:
                return "No repositories found for your account, sir."
            lines = []
            for r in repos:
                vis = "[private]" if r.get('isPrivate') else "[public]"
                full_name = r.get('nameWithOwner') or r.get('name')
                lang = f" ({r.get('primaryLanguage', {}).get('name')})" if r.get('primaryLanguage') and isinstance(r.get('primaryLanguage'), dict) and r.get('primaryLanguage', {}).get('name') else ""
                desc = f" - {r['description']}" if r.get('description') else ""
                lines.append(f"• {vis} {full_name}{lang}{desc}")
            return f"Your Repositories ({len(repos)}):\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing repos: {str(e)}"

    # === NOTIFICATIONS ===
    def notifications(self, limit=5) -> str:
        cmd = ['gh', 'api', 'notifications', '--jq', f'.[:{limit}] | .[] | .subject.title + " (" + .reason + ")"']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return "No notifications or error fetching them."
            output = result.stdout.strip()
            return f"GitHub notifications:\n{output}" if output else "No new notifications, sir."
        except Exception as e:
            return f"Error checking notifications: {str(e)}"
