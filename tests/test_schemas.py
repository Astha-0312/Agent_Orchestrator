import pytest
from pydantic import ValidationError
from schemas import (
    Subtask, TaskPlan, SpecialistOutput, ReviewResult, ToolCall, 
    EscalationRequest, MemoryEntry, TaskRecord
)

def test_subtask_creation():
    s = Subtask(id="1", specialist="research", description="test")
    assert s.id == "1"
    assert s.specialist == "research"
    assert s.description == "test"

def test_subtask_with_defaults():
    s = Subtask(id="1", specialist="writing", description="test")
    assert s.depends_on == []
    assert s.required_tools == []

def test_task_plan_validation():
    plan = TaskPlan(subtasks=[Subtask(id="1", specialist="research", description="test")], confidence=0.9)
    assert len(plan.subtasks) == 1
    assert plan.confidence == 0.9

def test_task_plan_confidence_bounds():
    with pytest.raises(ValidationError):
        TaskPlan(subtasks=[], confidence=1.5)
    with pytest.raises(ValidationError):
        TaskPlan(subtasks=[], confidence=-0.5)

def test_specialist_output_creation():
    out = SpecialistOutput(subtask_id="1", content="done")
    assert out.subtask_id == "1"
    assert out.content == "done"

def test_review_result_score_validation():
    with pytest.raises(ValidationError):
        ReviewResult(score=6, feedback="bad", passed=True)
    with pytest.raises(ValidationError):
        ReviewResult(score=0, feedback="bad", passed=False)
    res = ReviewResult(score=4, feedback="ok", passed=True)
    assert res.score == 4

def test_tool_call_creation():
    tc = ToolCall(tool_name="web_search", arguments={"q": "test"})
    assert tc.tool_name == "web_search"
    assert tc.arguments == {"q": "test"}
    assert tc.error is None

def test_tool_call_with_error():
    tc = ToolCall(tool_name="web_search", arguments={"q": "test"}, error="Timeout")
    assert tc.error == "Timeout"

def test_escalation_request_creation():
    er = EscalationRequest(reason="too hard", pending_subtasks=["2"])
    assert er.reason == "too hard"
    assert er.pending_subtasks == ["2"]

def test_memory_entry_defaults():
    me = MemoryEntry(content="mem")
    assert me.content == "mem"
    assert me.timestamp is not None
    assert me.importance is None

def test_task_record_defaults():
    tr = TaskRecord(task_id="t1", request="do it")
    assert tr.status == "pending"

def test_specialist_type_literals():
    s = Subtask(id="1", specialist="research", description="t")
    assert s.specialist == "research"

def test_approval_level_literals():
    pass
