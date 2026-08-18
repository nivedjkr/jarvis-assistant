import pytest
import subprocess
import asyncio

def test_gh_auth_status():
    import time
    r = None
    for _ in range(3):
        r = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            break
        time.sleep(1)
    assert r is not None and r.returncode == 0, f"gh CLI not authenticated: {r.stderr if r else ''}"

def test_gh_list_repos(tools):
    result = asyncio.run(
        tools.execute('gh_list_repos', {})
    )
    assert 'FAILED' not in result
    assert 'jarvis-assistant' in result.lower()
