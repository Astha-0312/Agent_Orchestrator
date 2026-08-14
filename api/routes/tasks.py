from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from api.models import CreateTaskRequest, CreateTaskResponse, TaskStatusResponse
from api.websocket import manager
import uuid
import json
import logging
import threading

logger = logging.getLogger("agent_orchestrator.api.routes.tasks")
router = APIRouter()

# In-memory task store (replaced by Redis in production)
_tasks = {}

@router.post("/tasks", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest):
    """Create and execute a new agent task."""
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "task_id": task_id,
        "request": req.prompt,
        "user_id": req.user_id,
        "status": "queued",
        "require_approval": req.require_approval,
    }
    
    # Run task in background thread
    def run_task():
        try:
            from graph import build_graph
            from memory.working import RedisWorkingMemory
            from tracing.tracer import ExecutionTracer
            
            _tasks[task_id]["status"] = "running"
            
            tracer = ExecutionTracer(task_id)
            working_mem = RedisWorkingMemory(task_id)
            
            app_graph = build_graph()
            initial_state = {
                "request": req.prompt,
                "plan": None,
                "current_subtask_index": 0,
                "subtask_outputs": {},
                "retry_count": 0,
                "reviewer_feedback": "",
                "trace": [],
                "final_output": None,
                "next_action": None,
                "confidence": 1.0,
                "escalation_requests": [],
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "memory_context": "",
                "tracer": tracer,
                "working_memory": working_mem,
            }
            
            result = app_graph.invoke(initial_state)
            
            _tasks[task_id].update({
                "status": "completed",
                "final_output": result.get("final_output"),
                "plan": result.get("plan"),
                "outputs": result.get("subtask_outputs", {}),
                "trace": result.get("trace", []),
                "total_cost_usd": result.get("total_cost_usd", 0),
                "total_tokens": result.get("total_tokens", 0),
            })
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = str(e)
    
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()
    
    return CreateTaskResponse(task_id=task_id, status="queued")

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status and results."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]

@router.get("/tasks")
async def list_tasks(limit: int = 50):
    """List all tasks."""
    tasks = list(_tasks.values())[-limit:]
    return {"tasks": tasks, "total": len(_tasks)}

@router.websocket("/ws/tasks/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    """WebSocket for real-time task events."""
    await manager.connect(websocket, task_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send ping/pong
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
