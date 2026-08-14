from fastapi import APIRouter, HTTPException
from api.models import ApprovalDecision, PendingApproval
from typing import List
import logging

logger = logging.getLogger("agent_orchestrator.api.routes.approvals")
router = APIRouter()

# In-memory approval queue
_pending_approvals = {}

def add_pending_approval(task_id: str, escalation: dict):
    """Called by graph when an escalation requires approval."""
    approval_id = f"{task_id}:{escalation.get('subtask_id', 'plan')}"
    _pending_approvals[approval_id] = {
        "task_id": task_id,
        **escalation,
    }

def get_approval_result(task_id: str, subtask_id: str = "plan") -> dict | None:
    """Check if an approval decision has been made."""
    approval_id = f"{task_id}:{subtask_id}"
    approval = _pending_approvals.get(approval_id)
    if approval and approval.get("decision"):
        return approval["decision"]
    return None

@router.get("/approvals/pending")
async def get_pending_approvals():
    """List all pending approval requests."""
    pending = [v for v in _pending_approvals.values() if not v.get("decision")]
    return {"approvals": pending, "total": len(pending)}

@router.post("/approvals/{task_id}/decide")
async def decide_approval(task_id: str, decision: ApprovalDecision):
    """Submit an approval decision."""
    matching = [k for k in _pending_approvals if k.startswith(task_id)]
    if not matching:
        raise HTTPException(status_code=404, detail="No pending approval for this task")
    
    for key in matching:
        _pending_approvals[key]["decision"] = decision.model_dump()
    
    return {"status": "decision_recorded", "task_id": task_id}

@router.get("/approvals/history")
async def get_approval_history(limit: int = 50):
    """Get approval history."""
    decided = [v for v in _pending_approvals.values() if v.get("decision")]
    return {"approvals": decided[-limit:], "total": len(decided)}
