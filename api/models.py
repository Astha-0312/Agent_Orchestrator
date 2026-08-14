from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CreateTaskRequest(BaseModel):
    prompt: str
    user_id: str = "default"
    require_approval: bool = False  # if True, always pause for plan approval

class CreateTaskResponse(BaseModel):
    task_id: str
    status: str = "queued"

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    request: str = ""
    plan: Optional[Dict] = None
    outputs: Dict[str, str] = {}
    escalations: List[Dict] = []
    final_output: Optional[str] = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    created_at: str = ""
    completed_at: Optional[str] = None

class ApprovalDecision(BaseModel):
    approved: bool
    feedback: Optional[str] = None
    action: str = "approve"  # approve, reject, take_over
    human_response: Optional[str] = None  # for take_over

class PendingApproval(BaseModel):
    task_id: str
    subtask_id: str = ""
    reason: str
    severity: int
    context: Dict[str, Any] = {}
    suggested_action: str = ""
    approval_level: str = "approve_action"
    created_at: str = ""

class MemoryDashboard(BaseModel):
    total_memories: int = 0
    by_collection: Dict[str, int] = {}
    recent_memories: List[Dict] = []

class TraceListItem(BaseModel):
    task_id: str
    request: str = ""
    status: str = ""
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    created_at: str = ""

class CostAnalytics(BaseModel):
    total_cost_usd: float = 0.0
    avg_cost_per_task: float = 0.0
    total_tasks: int = 0
    total_tokens: int = 0
    cost_by_day: List[Dict] = []

class ReplayRequest(BaseModel):
    modifications: List[Dict[str, Any]] = []
