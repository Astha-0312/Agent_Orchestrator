from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime
import uuid

SpecialistType = Literal["research", "writing", "data", "code"]
ApprovalLevel = Literal["notify", "approve_action", "approve_plan", "take_over"]
TaskStatus = Literal["queued", "running", "paused", "completed", "failed"]

class ToolCall(BaseModel):
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class Subtask(BaseModel):
    id: str = Field(description="Short unique id, e.g. 'subtask_1'")
    specialist: SpecialistType
    description: str
    depends_on: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)

class TaskPlan(BaseModel):
    subtasks: List[Subtask]
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

class SpecialistOutput(BaseModel):
    subtask_id: str
    specialist: SpecialistType
    output: str
    raw_data: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)

class ReviewResult(BaseModel):
    subtask_id: str
    score: int = Field(ge=1, le=5)
    feedback: str
    passed: bool

class EscalationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    subtask_id: str = ""
    reason: str
    severity: int = Field(ge=1, le=5)
    context: Dict[str, Any] = Field(default_factory=dict)
    suggested_action: str = ""
    approval_level: ApprovalLevel = "approve_action"
    status: str = "pending"  # pending, approved, rejected, taken_over
    human_response: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: Optional[str] = None
    access_count: int = 0

class TaskRecord(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request: str
    status: TaskStatus = "queued"
    plan: Optional[TaskPlan] = None
    outputs: Dict[str, str] = Field(default_factory=dict)
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    escalations: List[EscalationRequest] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    final_output: Optional[str] = None
