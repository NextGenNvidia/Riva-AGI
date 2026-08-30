import os
import sys
import subprocess
import platform
from orchestration.tools.registry import tool

COMMAND_BLACKLIST = [
    'rm -rf /',
    'rmdir /s /q c:',
    'format c:',
    'del /f /s /q c:',
    'mkfs',
    ':(){ :|:f };:',
    'chmod -R 777 /',
    'shutdown',
]

@tool(category='system')
def execute_command(command: str, timeout_seconds: int = 30) -> str:
    '''Executes a terminal/shell command on the system with a timeout and security safeguard.'''
    cmd_lower = command.lower().strip()
    for dangerous in COMMAND_BLACKLIST:
        if dangerous in cmd_lower:
            return f'Security Error: Command blocked by safety policy: "{command}"'
            
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=os.getcwd()
        )
        
        output_parts = []
        if res.stdout:
            output_parts.append(f'[stdout]\n{res.stdout.strip()}')
        if res.stderr:
            output_parts.append(f'[stderr]\n{res.stderr.strip()}')
        if not output_parts:
            output_parts.append('(No output produced)')
            
        output_parts.append(f'[exit code: {res.returncode}]')
        return '\n'.join(output_parts)
    except subprocess.TimeoutExpired:
        return f'Error: Command timed out after {timeout_seconds} seconds.'
    except Exception as e:
        return f'Error executing command: {e}'
    
@tool(category='system')
def get_system_info() -> str:
    '''Returns current OS, Python version, working directory, and environment details.'''
    return (
        f'OS: {platform.system()} {platform.release()} ({platform.version()})\n'
        f'Platform: {platform.platform()}\n'
        f'Python: {sys.version.split()[0]}\n'
        f'Working Directory: {os.getcwd()}'
    )
