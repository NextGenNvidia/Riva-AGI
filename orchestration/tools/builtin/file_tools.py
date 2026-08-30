import os
from typing import Optional
from orchestration.tools.registry import tool

@tool(category='file')
def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    '''Reads contents of a text file from disk. Optionally specify start_line and end_line (1-indexed).'''
    if not os.path.exists(file_path):
        return f'Error: File not found at path: {file_path}'
    if os.path.isdir(file_path):
        return f'Error: Path is a directory, not a file: {file_path}'
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if start_line is not None or end_line is not None:
            start = max(1, start_line or 1) - 1
            end = min(len(lines), end_line or len(lines))
            selected_lines = lines[start:end]
            numbered = [f"{i+1:4d} | {line}" for i, line in enumerate(selected_lines, start=start)]
            return ''.join(numbered)
        else:
            return ''.join(lines)
    except Exception as e:
        return f'Error reading file {file_path}: {e}'

@tool(category='file')
def write_file(file_path: str, content: str, overwrite: bool = True) -> str:
    '''Creates or overwrites a file on disk with the provided text content.'''
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        if os.path.exists(file_path) and not overwrite:
            return f'Error: File {file_path} already exists and overwrite is set to False.'
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f'Success: Successfully wrote {len(content)} characters to {file_path}.'
    except Exception as e:
        return f'Error writing to file {file_path}: {e}'

@tool(category='file')
def edit_file(file_path: str, target_content: str, replacement_content: str) -> str:
    '''Replaces an exact occurrence of target_content with replacement_content in a file.'''
    if not os.path.exists(file_path):
        return f'Error: File {file_path} not found.'
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
            
        if target_content not in full_text:
            return f'Error: target_content not found in {file_path}.'
            
        count = full_text.count(target_content)
        if count > 1:
            return f'Warning: target_content occurs {count} times. Please specify more unique context.'
            
        new_text = full_text.replace(target_content, replacement_content, 1)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        return f'Success: Successfully updated {file_path}.'
    except Exception as e:
        return f'Error editing file {file_path}: {e}'

@tool(category='file')
def list_directory(dir_path: str = '.', recursive: bool = False, max_items: int = 50) -> str:
    '''Lists files and subdirectories within a specified directory.'''
    if not os.path.exists(dir_path):
        return f'Error: Directory {dir_path} not found.'
    if not os.path.isdir(dir_path):
        return f'Error: Path is not a directory: {dir_path}'
        
    results = []
    try:
        if not recursive:
            items = os.listdir(dir_path)
            for item in items[:max_items]:
                full = os.path.join(dir_path, item)
                kind = '[DIR] ' if os.path.isdir(full) else '[FILE]'
                size = f'{os.path.getsize(full)} bytes' if os.path.isfile(full) else ''
                results.append(f'{kind} {item} {size}'.strip())
        else:
            count = 0
            for root, dirs, files in os.walk(dir_path):
                rel_root = os.path.relpath(root, dir_path)
                if rel_root != '.':
                    results.append(f'[DIR]   {rel_root}')
                for f in files:
                    results.append(f'[FILE] {os.path.join(rel_root, f)}')
                    count += 1
                    if count >= max_items:
                        results.append(f'... (truncated at {max_items} items)')
                        break
                if count >= max_items:
                    break
        return '\n'.join(results) if results else 'Directory is empty.'
    except Exception as e:
        return f'Error listing directory {dir_path}: {e}'
