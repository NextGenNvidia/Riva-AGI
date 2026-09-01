import os
import pytest
from orchestration.tools import tool_registry
from orchestration.tools.builtin.file_tools import (
    read_file,
    write_file,
    edit_file,
    list_directory,
)


def test_file_tools_registered():
    tools = tool_registry.get_all_tools()
    assert "read_file" in tools
    assert "write_file" in tools
    assert "edit_file" in tools
    assert "list_directory" in tools
    
    assert tools["read_file"].category == "file"
    assert tools["write_file"].category == "file"
    assert tools["edit_file"].category == "file"
    assert tools["list_directory"].category == "file"


def test_write_and_read_file(tmp_path):
    test_file = str(tmp_path / "subdir" / "test.txt")
    
    # Write file
    write_res = write_file(test_file, "Line 1\nLine 2\nLine 3\n")
    assert "Success" in write_res
    assert os.path.exists(test_file)
    
    # Read full file
    content = read_file(test_file)
    assert content == "Line 1\nLine 2\nLine 3\n"
    
    # Read line slice
    slice_content = read_file(test_file, start_line=2, end_line=2)
    assert "2 | Line 2" in slice_content


def test_write_file_no_overwrite(tmp_path):
    test_file = str(tmp_path / "exist.txt")
    write_file(test_file, "original")
    
    res = write_file(test_file, "new", overwrite=False)
    assert "Error: File" in res
    assert "already exists" in res
    assert read_file(test_file) == "original"


def test_read_file_errors(tmp_path):
    # Non-existent
    assert "Error: File not found" in read_file(str(tmp_path / "missing.txt"))
    
    # Directory path
    assert "Error: Path is a directory" in read_file(str(tmp_path))


def test_edit_file(tmp_path):
    test_file = str(tmp_path / "code.py")
    write_file(test_file, "def hello():\n    return 'world'\n")
    
    # Successful edit
    edit_res = edit_file(test_file, "return 'world'", "return 'RIVA'")
    assert "Success" in edit_res
    assert "return 'RIVA'" in read_file(test_file)
    
    # Target not found
    err_res = edit_file(test_file, "non_existent", "abc")
    assert "Error: target_content not found" in err_res
    
    # Multiple occurrences warning
    write_file(test_file, "foo bar foo")
    warn_res = edit_file(test_file, "foo", "baz")
    assert "Warning: target_content occurs 2 times" in warn_res


def test_list_directory(tmp_path):
    # Setup dir structure
    (tmp_path / "file1.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file2.txt").write_text("world")
    
    # Non-recursive
    listed = list_directory(str(tmp_path), recursive=False)
    assert "file1.txt" in listed
    assert "sub" in listed
    
    # Recursive
    listed_rec = list_directory(str(tmp_path), recursive=True)
    assert "file1.txt" in listed_rec
    assert "file2.txt" in listed_rec
    
    # Error cases
    assert "Error: Directory" in list_directory(str(tmp_path / "non_existent"))
    assert "Error: Path is not a directory" in list_directory(str(tmp_path / "file1.txt"))


def test_tool_registry_execute_file_tool(tmp_path):
    test_file = str(tmp_path / "registry_test.txt")
    res = tool_registry.execute("write_file", file_path=test_file, content="Registry execution test")
    assert "Success" in res
    
    read_res = tool_registry.execute("read_file", file_path=test_file)
    assert read_res == "Registry execution test"
