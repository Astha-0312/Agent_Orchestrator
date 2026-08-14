import os
from .registry import default_registry

def _is_safe_path(path: str) -> bool:
    """Ensure path is within current working directory."""
    cwd = os.path.abspath(os.getcwd())
    abs_path = os.path.abspath(path)
    return abs_path.startswith(cwd)

def read_file(path: str) -> str:
    if not _is_safe_path(path):
        return f"Error: Path '{path}' is outside the current working directory."
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    if not _is_safe_path(path):
        return f"Error: Path '{path}' is outside the current working directory."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_directory(path: str = ".") -> str:
    if not _is_safe_path(path):
        return f"Error: Path '{path}' is outside the current working directory."
    try:
        items = os.listdir(path)
        if not items:
            return "Directory is empty."
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

default_registry.register("read_file", read_file, "Read text from a file. Restricted to CWD.", {"path": "string"})
default_registry.register("write_file", write_file, "Write text to a file. Restricted to CWD.", {"path": "string", "content": "string"})
default_registry.register("list_directory", list_directory, "List files in a directory. Restricted to CWD.", {"path": "string (optional, default '.')"})
