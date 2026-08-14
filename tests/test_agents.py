import pytest
from unittest.mock import patch, MagicMock
from schemas import TaskPlan, SpecialistOutput, ReviewResult
from agents import (
    supervisor_plan, run_research_specialist, run_writing_specialist,
    run_data_specialist, run_code_specialist, review_output
)

def test_supervisor_plan_basic(mock_groq_json_response, sample_plan):
    with patch("agents.call_llm_json") as mock_llm:
        mock_llm.return_value = (sample_plan, {"prompt_tokens": 10, "completion_tokens": 20})
        plan, usage = supervisor_plan("do something", [])
        assert plan.confidence == 0.85
        assert len(plan.subtasks) == 2

def test_supervisor_plan_with_memory_context():
    with patch("agents.call_llm_json") as mock_llm:
        mock_llm.return_value = ({"subtasks": [], "confidence": 0.9}, {"prompt_tokens": 5, "completion_tokens": 10})
        plan, usage = supervisor_plan("test", ["mem1", "mem2"])
        assert plan.confidence == 0.9

def test_research_specialist():
    with patch("agents.default_registry.invoke") as mock_tool:
        mock_tool.return_value = "search result"
        with patch("agents.call_llm") as mock_llm:
            mock_llm.return_value = ("research done", {"prompt_tokens": 10, "completion_tokens": 20})
            out, usage = run_research_specialist("1", "desc", {}, "")
            assert out.content == "research done"

def test_writing_specialist():
    with patch("agents.call_llm") as mock_llm:
        mock_llm.return_value = ("written content", {"prompt_tokens": 10, "completion_tokens": 20})
        out, usage = run_writing_specialist("2", "desc", {}, "")
        assert out.content == "written content"

def test_data_specialist():
    with patch("agents.call_llm") as mock_llm:
        mock_llm.return_value = ("data processed", {"prompt_tokens": 10, "completion_tokens": 20})
        out, usage = run_data_specialist("3", "desc", {}, "")
        assert out.content == "data processed"

def test_code_specialist():
    with patch("agents.default_registry.invoke") as mock_tool:
        mock_tool.return_value = "code executed"
        with patch("agents.call_llm") as mock_llm:
            mock_llm.return_value = ("code written", {"prompt_tokens": 10, "completion_tokens": 20})
            out, usage = run_code_specialist("4", "desc", {}, "")
            assert out.content == "code written"

def test_reviewer_pass(sample_review_pass):
    with patch("agents.call_llm_json") as mock_llm:
        mock_llm.return_value = (sample_review_pass, {"prompt_tokens": 10, "completion_tokens": 20})
        res, _ = review_output("1", "desc", "out")
        assert res.passed is True
        assert res.score == 4

def test_reviewer_fail(sample_review_fail):
    with patch("agents.call_llm_json") as mock_llm:
        mock_llm.return_value = (sample_review_fail, {"prompt_tokens": 10, "completion_tokens": 20})
        res, _ = review_output("1", "desc", "out")
        assert res.passed is False

def test_call_llm_json_parse_error_recovery():
    with patch("agents.groq_client.chat.completions.create") as mock_create:
        mock_create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="not json"))])
        with pytest.raises(ValueError):
            review_output("1", "desc", "out")

def test_call_llm_cost_tracking():
    with patch("agents.call_llm") as mock_llm:
        mock_llm.return_value = ("test", {"prompt_tokens": 100, "completion_tokens": 50})
        out, usage = run_writing_specialist("1", "desc", {}, "")
        assert usage["prompt_tokens"] == 100
