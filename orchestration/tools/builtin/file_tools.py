"""
File System Tools — orchestration/tools/builtin/file_tools.py
==============================================================
Standard file manipulation tools for Riva-AGI agents (Coder, Data, System).
"""

import os
from pathlib import Path
from typing import List
from orchestration.tools.base import tool
from orchestration.tools.registry import tool_registry


@tool(
    name="read_file",
    description="Read the complete text contents of a file at the specified path.",
    category="file",
    tags=["file", "read", "filesystem"],
)
def read_file(file_path: str) -> str:
    """Reads and returns text from a file."""
    path = Path(file_path)
    if not path.exists():
        return f"Error: File '{file_path}' does not exist."
    if not path.is_file():
        return f"Error: Path '{file_path}' is a directory, not a file."
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"


@tool(
    name="write_file",
    description="Write content to a file at the specified path. Creates parent directories if needed.",
    category="file",
    tags=["file", "write", "create"],
)
def write_file(file_path: str, content: str) -> str:
    """Writes text content to a file, creating parent directories if necessary."""
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to '{file_path}'."
    except Exception as e:
        return f"Error writing file '{file_path}': {str(e)}"


@tool(
    name="list_directory",
    description="List files and subdirectories within a given directory path.",
    category="file",
    tags=["file", "directory", "list"],
)
def list_directory(dir_path: str = ".") -> str:
    """Lists files and directories at dir_path."""
    path = Path(dir_path)
    if not path.exists():
        return f"Error: Directory '{dir_path}' does not exist."
    if not path.is_dir():
        return f"Error: Path '{dir_path}' is a file, not a directory."
    try:
        items = []
        for item in sorted(path.iterdir()):
            item_type = "[DIR]" if item.is_dir() else "[FILE]"
            items.append(f"{item_type} {item.name}")
        return "\n".join(items) if items else "(Empty directory)"
    except Exception as e:
        return f"Error listing directory '{dir_path}': {str(e)}"


@tool(
    name="file_exists",
    description="Check whether a file or directory exists at the given path.",
    category="file",
    tags=["file", "check"],
)
def file_exists(file_path: str) -> str:
    """Checks if a file exists."""
    path = Path(file_path)
    exists = path.exists()
    file_type = "directory" if path.is_dir() else "file"
    return f"{'Yes' if exists else 'No'}, {file_path} {'exists as a ' + file_type if exists else 'does not exist'}."


# Register file tools into global registry
tool_registry.register(read_file)
tool_registry.register(write_file)
tool_registry.register(list_directory)
tool_registry.register(file_exists)
