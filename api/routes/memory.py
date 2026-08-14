from fastapi import APIRouter, HTTPException
from api.models import MemoryDashboard
import logging

logger = logging.getLogger("agent_orchestrator.api.routes.memory")
router = APIRouter()

def _get_memory_manager():
    from memory.semantic import SemanticMemory
    from memory.management import MemoryManager
    sm = SemanticMemory()
    return MemoryManager(sm)

@router.get("/memory/dashboard")
async def get_memory_dashboard(user_id: str = "default"):
    """Get memory dashboard data."""
    try:
        mgr = _get_memory_manager()
        data = mgr.get_dashboard_data(user_id)
        return data
    except Exception as e:
        logger.error(f"Memory dashboard error: {e}")
        return {"total_memories": 0, "by_collection": {}, "recent_memories": [], "error": str(e)}

@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str, collection: str = "task_outcomes"):
    """Delete a specific memory."""
    try:
        mgr = _get_memory_manager()
        success = mgr.delete_memory(memory_id, collection)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/memory/user/{user_id}")
async def delete_user_memories(user_id: str):
    """Delete all memories for a user."""
    try:
        from memory.semantic import SemanticMemory
        sm = SemanticMemory()
        count = sm.delete_user_data(user_id)
        return {"status": "deleted", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/memory/consolidate")
async def consolidate_memories():
    """Run memory consolidation."""
    try:
        mgr = _get_memory_manager()
        count = mgr.consolidate()
        return {"status": "consolidated", "merged_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/memory/expire")
async def expire_old_memories(max_age_days: int = 30, min_importance: float = 0.3):
    """Expire old low-importance memories."""
    try:
        mgr = _get_memory_manager()
        count = mgr.expire_old(max_age_days, min_importance)
        return {"status": "expired", "expired_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
