import pytest
import subprocess
import asyncio

def test_gh_auth_status():
    r = subprocess.run(
        ['gh', 'auth', 'status'],
        capture_output=True, text=True
    )
    assert r.returncode == 0, "gh CLI not authenticated"

def test_gh_list_repos(tools):
    result = asyncio.run(
        tools.execute('gh_list_repos', {})
    )
    assert 'FAILED' not in result
    assert 'jarvis-assistant' in result.lower()
