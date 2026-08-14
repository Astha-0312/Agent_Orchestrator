import pytest
from unittest.mock import patch, MagicMock
from tracing import ExecutionTracer, TraceStorage, ReplayEngine, TraceAnalytics

def test_tracer_start_end_span():
    tracer = ExecutionTracer()
    span = tracer.start_span("test")
    tracer.end_span(span.id)
    assert span.end_time is not None

def test_tracer_nested_spans():
    tracer = ExecutionTracer()
    p = tracer.start_span("parent")
    c = tracer.start_span("child", parent_id=p.id)
    assert c.parent_id == p.id

def test_tracer_to_tree():
    tracer = ExecutionTracer()
    p = tracer.start_span("parent")
    c = tracer.start_span("child", parent_id=p.id)
    tree = tracer.to_tree()
    assert tree["name"] == "parent"
    assert len(tree["children"]) == 1

def test_tracer_cost_tracking():
    tracer = ExecutionTracer()
    span = tracer.start_span("test")
    span.add_cost(0.05)
    assert span.cost == 0.05

def test_storage_save_and_get_trace():
    storage = TraceStorage("sqlite:///:memory:")
    storage.save_trace("t1", {"spans": []})
    assert storage.get_trace("t1") is not None

def test_storage_list_traces():
    storage = TraceStorage("sqlite:///:memory:")
    assert isinstance(storage.list_traces(), list)

def test_storage_save_spans():
    storage = TraceStorage("sqlite:///:memory:")
    storage.save_spans("t1", [])

def test_analytics_cost_summary():
    analytics = TraceAnalytics()
    with patch.object(analytics.storage, "list_traces", return_value=[{"cost": 1.0}]):
        assert analytics.get_total_cost() == 1.0

def test_replay_load_execution():
    replay = ReplayEngine()
    with patch.object(replay.storage, "get_trace", return_value={"spans": []}):
        assert replay.load("t1") is not None

def test_replay_compare():
    replay = ReplayEngine()
    assert isinstance(replay.compare("t1", "t2"), dict)
