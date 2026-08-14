import pytest
import os
import json
from unittest.mock import MagicMock

# Set test env vars before importing anything
os.environ["GROQ_API_KEY"] = "test-key-not-real"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use DB 15 for tests
os.environ["CHROMADB_PATH"] = "./test_chromadb_data"
os.environ["DATABASE_URL"] = "sqlite:///test_agent.db"

@pytest.fixture
def mock_groq_json_response():
    # Returns a factory that creates mock Groq responses with JSON content
    def _create(content_dict, input_tokens=10, output_tokens=20):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(content_dict)
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = input_tokens
        mock_response.usage.completion_tokens = output_tokens
        return mock_response
    return _create

@pytest.fixture
def mock_groq_text_response():
    def _create(text, input_tokens=10, output_tokens=20):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = text
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = input_tokens
        mock_response.usage.completion_tokens = output_tokens
        return mock_response
    return _create

@pytest.fixture
def sample_plan():
    return {
        "subtasks": [
            {"id": "subtask_1", "specialist": "research", "description": "Search for X", "depends_on": [], "required_tools": ["web_search"]},
            {"id": "subtask_2", "specialist": "writing", "description": "Summarize findings", "depends_on": ["subtask_1"], "required_tools": []},
        ],
        "confidence": 0.85
    }

@pytest.fixture
def sample_review_pass():
    return {"score": 4, "feedback": "Good output", "passed": True}

@pytest.fixture
def sample_review_fail():
    return {"score": 2, "feedback": "Output is incomplete", "passed": False}
