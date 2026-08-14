import pytest
import os
from unittest.mock import patch, MagicMock
from tools import default_registry

def test_registry_register_and_list():
    assert "web_search" in default_registry.list_tools()

def test_registry_invoke_success():
    with patch("tools.web_search") as mock_tool:
        mock_tool.return_value = "results"
        default_registry.register("mock_search", mock_tool, "search tool")
        res = default_registry.invoke("mock_search", {"q": "test"})
        assert res == "results"

def test_registry_invoke_missing_tool():
    with pytest.raises(ValueError):
        default_registry.invoke("non_existent", {})

def test_registry_invoke_error_handling():
    with patch("tools.web_search") as mock_tool:
        mock_tool.side_effect = Exception("failed")
        default_registry.register("mock_fail", mock_tool, "fail")
        with pytest.raises(Exception, match="failed"):
            default_registry.invoke("mock_fail", {})

def test_registry_get_tool_descriptions():
    desc = default_registry.get_tool_descriptions()
    assert isinstance(desc, dict)

def test_web_search_timeout():
    with patch("tools.web_search.ddgs") as mock_ddgs:
        mock_ddgs.side_effect = TimeoutError()
        with pytest.raises(TimeoutError):
            default_registry.invoke("web_search", {"query": "test"})

def test_web_search_no_results():
    with patch("tools.web_search.ddgs") as mock_ddgs:
        mock_ddgs.return_value = []
        res = default_registry.invoke("web_search", {"query": "test"})
        assert res == "No results found."

def test_file_io_read_write(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    with patch("os.getcwd", return_value=str(tmp_path)):
        res = default_registry.invoke("file_io", {"action": "read", "path": "test.txt"})
        assert res == "hello"

def test_file_io_security(tmp_path):
    with patch("os.getcwd", return_value=str(tmp_path)):
        with pytest.raises(PermissionError):
            default_registry.invoke("file_io", {"action": "read", "path": "../out_of_bounds.txt"})

def test_code_exec_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Hello World"
        mock_run.return_value.returncode = 0
        res = default_registry.invoke("code_exec", {"code": "print('Hello World')"})
        assert res == "Hello World"

def test_code_exec_timeout():
    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=5)
        with pytest.raises(TimeoutError):
            default_registry.invoke("code_exec", {"code": "while True: pass"})

def test_code_exec_error():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stderr = "SyntaxError: invalid syntax"
        mock_run.return_value.returncode = 1
        res = default_registry.invoke("code_exec", {"code": "print(Hello World)"})
        assert "SyntaxError" in res

def test_db_query_select_only():
    with pytest.raises(ValueError):
        default_registry.invoke("db_query", {"query": "DROP TABLE users;"})

def test_api_get_success():
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"key": "value"}
        mock_get.return_value.status_code = 200
        res = default_registry.invoke("api_call", {"method": "GET", "url": "http://test.com"})
        assert res == {"key": "value"}

def test_api_post_success():
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"created": True}
        mock_post.return_value.status_code = 201
        res = default_registry.invoke("api_call", {"method": "POST", "url": "http://test.com", "data": {"a": 1}})
        assert res == {"created": True}
