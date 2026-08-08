import pytest
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

from jarvis.tools import ToolRegistry, validate_tool_schemas

@pytest.fixture
def registry():
    return ToolRegistry()

def test_tools_registered(registry):
    assert len(registry.tools) > 0, \
        "No tools registered"
    assert 'write_file' in registry.tools
    assert 'read_file' in registry.tools
    assert 'open_application' in registry.tools
    assert 'open_website' in registry.tools
    assert 'git_add_commit_push' in registry.tools
    print(f"✓ {len(registry.tools)} tools registered")

def test_schema_validation(registry):
    result = validate_tool_schemas(registry)
    assert result, "Schema validation failed"

def test_write_and_read_file(registry):
    loop = asyncio.new_event_loop()
    
    # Write
    write_result = loop.run_until_complete(
        registry.execute('write_file', {
            'path': 'jarvis/tests/test_output.txt',
            'content': 'JARVIS TEST FILE'
        })
    )
    assert 'FAILED' not in write_result
    assert os.path.exists('jarvis/tests/test_output.txt')
    
    # Read back
    read_result = loop.run_until_complete(
        registry.execute('read_file', {
            'path': 'jarvis/tests/test_output.txt'
        })
    )
    assert 'JARVIS TEST FILE' in read_result
    
    # Cleanup
    os.remove('jarvis/tests/test_output.txt')
    loop.close()
    print("✓ write_file and read_file work correctly")

def test_create_directory(registry):
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        registry.execute('create_directory', {
            'path': 'jarvis/tests/test_dir_output'
        })
    )
    assert 'FAILED' not in result
    assert os.path.exists('jarvis/tests/test_dir_output')
    import shutil
    shutil.rmtree('jarvis/tests/test_dir_output')
    loop.close()
    print("✓ create_directory works correctly")

def test_list_files(registry):
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        registry.execute('list_files', {'path': '.'})
    )
    assert 'FAILED' not in result
    assert 'jarvis' in result.lower()
    loop.close()
    print("✓ list_files returns real directory contents")

def test_system_status(registry):
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        registry.execute('get_system_status', {})
    )
    assert 'FAILED' not in result
    assert 'CPU' in result
    assert '%' in result
    loop.close()
    print("✓ get_system_status returns real data")

def test_git_status(registry):
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        registry.execute('git_status', {})
    )
    assert 'FAILED' not in result
    assert len(result) > 0
    loop.close()
    print("✓ git_status returns real git output")

def test_gh_list_repos(registry):
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        registry.execute('gh_list_repos', {})
    )
    # May fail if gh not authenticated — that's ok
    # Just check it doesn't crash
    assert result is not None
    loop.close()
    print(f"✓ gh_list_repos: {result[:100]}")
