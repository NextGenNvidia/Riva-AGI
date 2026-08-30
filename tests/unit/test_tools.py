import os
import pytest
import tempfile
from orchestration.tools import (
    tool_registry,
    read_file,
    write_file,
    edit_file,
    list_directory,
    execute_command,
    get_system_info,
)

def test_registry_registration():
    all_tools = tool_registry.get_all_tools()
    assert 'read_file' in all_tools
    assert 'write_file' in all_tools
    assert 'execute_command' in all_tools
    assert 'web_search' in all_tools

def test_file_write_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, 'test.txt')
        
        # Test write
        res_write = write_file(test_file, 'Hello World\nLine 2\nLine 3')
        assert 'Success' in res_write
        assert os.path.exists(test_file)
        
        # Test full read
        content = read_file(test_file)
        assert 'Hello World' in content
        assert 'Line 3' in content
        
        # Test line range read
        ranged = read_file(test_file, start_line=2, end_line=2)
        assert 'Line 2' in ranged
        assert 'Line 3' not in ranged

def test_file_edit():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, 'code.py')
        write_file(test_file, 'def foo():Xn    return 42\n')
        
        res_edit = edit_file(test_file, target_content='return 42', replacement_content='return 100')
        assert 'Success' in res_edit
        
        updated = read_file(test_file)
        assert 'return 100' in updated

def test_list_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        write_file(os.path.join(tmpdir, 'a.txt'), 'aaa')
        write_file(os.path.join(tmpdir, 'b.txt'), 'bbb')
        
        listing = list_directory(tmpdir)
        assert 'a.txt' in listing
        assert 'b.txt' in listing

def test_system_info():
    info = get_system_info()
    assert 'OS:' in info
    assert 'Python:' in info

def test_execute_command():
    res = execute_command('echo hello')
    assert 'hello' in res
    assert 'exit code: 0' in res

def test_execute_command_blacklist():
    res = execute_command('rm -rf /')
    assert 'Security Error' in res
