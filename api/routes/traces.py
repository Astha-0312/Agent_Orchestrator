from fastapi import APIRouter, HTTPException
from api.models import TraceListItem, CostAnalytics, ReplayRequest
import logging

logger = logging.getLogger("agent_orchestrator.api.routes.traces")
router = APIRouter()

def _get_storage():
    from tracing.storage import TraceStorage
    return TraceStorage()

def _get_analytics():
    from tracing.storage import TraceStorage
    from tracing.analytics import TraceAnalytics
    return TraceAnalytics(_get_storage())

@router.get("/traces")
async def list_traces(limit: int = 50, offset: int = 0):
    """List recent execution traces."""
    try:
        storage = _get_storage()
        traces = storage.list_traces(limit, offset)
        return {"traces": traces, "total": len(traces)}
    except Exception as e:
        return {"traces": [], "total": 0, "error": str(e)}

@router.get("/traces/{task_id}")
async def get_trace(task_id: str):
    """Get full execution trace for a task."""
    storage = _get_storage()
    trace = storage.get_trace(task_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace

@router.get("/traces/{task_id}/spans/{span_id}")
async def get_span(task_id: str, span_id: str):
    """Get a single span with full prompt/response."""
    storage = _get_storage()
    span = storage.get_span(span_id)
    if not span:
        raise HTTPException(status_code=404, detail="Span not found")
    return span

@router.post("/traces/{task_id}/replay")
async def replay_trace(task_id: str, req: ReplayRequest):
    """Replay a past execution with modifications."""
    try:
        from tracing.replay import ReplayEngine, StepModification
        storage = _get_storage()
        engine = ReplayEngine(storage)
        
        modifications = []
        for mod in req.modifications:
            modifications.append(StepModification(
                span_id=mod.get("span_id", ""),
                modification_type=mod.get("type", "override_output"),
                value=mod.get("value")
            ))
        
        result = engine.replay(task_id, modifications)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/costs")
async def get_cost_analytics(days: int = 30):
    """Get cost and performance analytics."""
    try:
        analytics = _get_analytics()
        return analytics.get_cost_summary(days)
    except Exception as e:
        return {"error": str(e), "total_cost_usd": 0, "total_tasks": 0}

@router.get("/analytics/performance")
async def get_performance_analytics(days: int = 30):
    """Get performance analytics."""
    try:
        analytics = _get_analytics()
        return analytics.get_performance_summary(days)
    except Exception as e:
        return {"error": str(e)}

@router.delete("/traces/{task_id}")
async def delete_trace(task_id: str):
    """Delete a trace."""
    storage = _get_storage()
    success = storage.delete_trace(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"status": "deleted"}
