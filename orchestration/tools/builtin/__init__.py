"""
Builtin Tools Suite for Riva-AGI
================================
Importing this package registers all default built-in tools.
"""

from orchestration.tools.builtin.file_tools import (
    read_file,
    write_file,
    list_directory,
    file_exists,
)
from orchestration.tools.builtin.code_tools import (
    execute_python_code,
    check_python_syntax,
    run_pytest,
)
from orchestration.tools.builtin.web_tools import (
    web_search,
    fetch_webpage,
)
from orchestration.tools.builtin.system_tools import (
    get_current_time,
    calculate,
    get_system_info,
)

__all__ = [
    "read_file",
    "write_file",
    "list_directory",
    "file_exists",
    "execute_python_code",
    "check_python_syntax",
    "run_pytest",
    "web_search",
    "fetch_webpage",
    "get_current_time",
    "calculate",
    "get_system_info",
]
