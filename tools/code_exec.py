import subprocess
import tempfile
import os
from .registry import default_registry

MAX_OUTPUT_LENGTH = 10 * 1024  # 10 KB

def _truncate_output(output: str) -> str:
    if len(output) > MAX_OUTPUT_LENGTH:
        return output[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"
    return output

def execute_python(code: str, timeout: int = 30) -> str:
    """Executes Python code via subprocess."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['python', temp_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        return _truncate_output(output)
    except subprocess.TimeoutExpired:
        return f"Error: Execution timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing python: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def execute_shell(command: str, timeout: int = 30) -> str:
    """Executes a shell command via subprocess."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        return _truncate_output(output)
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing shell command: {str(e)}"

default_registry.register("execute_python", execute_python, "Execute python code safely.", {"code": "string", "timeout": "int (optional)"})
default_registry.register("execute_shell", execute_shell, "Execute shell command safely.", {"command": "string", "timeout": "int (optional)"})
