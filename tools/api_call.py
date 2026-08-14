import requests
from .registry import default_registry

def api_get(url: str, headers: dict = None, timeout: int = 30) -> str:
    """Performs an HTTP GET request."""
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error during GET request: {str(e)}"

def api_post(url: str, data: dict = None, headers: dict = None, timeout: int = 30) -> str:
    """Performs an HTTP POST request."""
    try:
        response = requests.post(url, json=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error during POST request: {str(e)}"

default_registry.register("api_get", api_get, "Perform HTTP GET request.", {"url": "string", "headers": "dict (optional)", "timeout": "int (optional)"})
default_registry.register("api_post", api_post, "Perform HTTP POST request.", {"url": "string", "data": "dict (optional)", "headers": "dict (optional)", "timeout": "int (optional)"})
