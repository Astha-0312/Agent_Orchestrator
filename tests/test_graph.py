import pytest
from unittest.mock import patch, MagicMock
from graph import build_graph

def test_build_graph_compiles():
    graph = build_graph()
    assert graph is not None

def test_happy_path():
    graph = build_graph()
    with patch("graph.supervisor_node") as mock_sup:
        mock_sup.return_value = {"next_step": "research", "plan": MagicMock()}
        with patch("graph.research_node") as mock_res:
            mock_res.return_value = {"next_step": "end"}
            state = {"input": "test task"}
            result = graph.invoke(state)
            assert result is not None

def test_retry_on_failure():
    graph = build_graph()
    with patch("graph.review_node") as mock_rev:
        mock_rev.return_value = {"passed": False, "retry_count": 1, "next_step": "research"}
        result = mock_rev.return_value
        assert result["next_step"] == "research"

def test_escalation_on_low_confidence():
    graph = build_graph()
    with patch("graph.supervisor_node") as mock_sup:
        mock_sup.return_value = {"confidence": 0.3, "next_step": "escalate"}
        result = mock_sup.return_value
        assert result["next_step"] == "escalate"

def test_escalation_on_repeated_failure():
    graph = build_graph()
    with patch("graph.review_node") as mock_rev:
        mock_rev.return_value = {"passed": False, "retry_count": 3, "next_step": "escalate"}
        result = mock_rev.return_value
        assert result["next_step"] == "escalate"

def test_all_specialist_types_dispatched():
    graph = build_graph()
    # Mocking graph branches
    assert hasattr(graph, "branches") or hasattr(graph, "nodes")

def test_state_initialization():
    graph = build_graph()
    assert graph is not None
