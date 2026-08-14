"""
Agent Orchestrator — Main Entry Point

Usage:
  python main.py                    # Run default demo task
  python main.py "your request"     # Run a custom request
  python main.py --server           # Start the API server
  python main.py --demo             # Run the full demo scenario
"""
import os
import sys
import json
import logging
import webbrowser
import threading

def run_task(request: str):
    """Run a single task through the orchestrator."""
    from config import get_settings, setup_logging
    from graph import build_graph
    from tracing.tracer import ExecutionTracer
    from memory.working import RedisWorkingMemory
    import uuid
    
    setup_logging()
    settings = get_settings()
    
    if not settings.GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set. Copy .env.example to .env and add your key.")
        return
    
    task_id = str(uuid.uuid4())[:8]
    print(f"Task ID: {task_id}")
    print(f"Request: {request}")
    print(f"Model: {settings.MODEL_NAME}")
    print("=" * 60)
    
    tracer = ExecutionTracer(task_id)
    working_mem = RedisWorkingMemory(task_id)
    
    app = build_graph()
    initial_state = {
        "request": request,
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
    
    final_state = app.invoke(initial_state)
    
    # Print results
    print("\n" + "=" * 60)
    print("PLAN:")
    if final_state.get("plan"):
        for st in final_state["plan"].subtasks:
            print(f"  [{st.id}] ({st.specialist}) {st.description}")
        print(f"  Confidence: {final_state['plan'].confidence}")
    
    print("\nTRACE:")
    for i, entry in enumerate(final_state.get("trace", []), 1):
        detail_str = json.dumps(entry['detail'], default=str)[:150]
        print(f"  {i}. {entry['event']}: {detail_str}")
    
    if final_state.get("escalation_requests"):
        print("\nESCALATIONS:")
        for esc in final_state["escalation_requests"]:
            print(f"  - [{esc.get('severity', '?')}] {esc.get('reason', '')}")
    
    print(f"\nCOST: ${final_state.get('total_cost_usd', 0):.6f}")
    print(f"TOKENS: {final_state.get('total_tokens', 0):,}")
    print(f"\nFINAL OUTPUT:")
    print(final_state.get("final_output", "No output"))
    
    return final_state


def run_server():
    """Start the FastAPI server."""
    import uvicorn
    from config import get_settings

    settings = get_settings()

    url = f"http://localhost:{settings.API_PORT}/review"

    print(f"Starting Agent Orchestrator API on {settings.API_HOST}:{settings.API_PORT}")
    print(f"Docs: http://localhost:{settings.API_PORT}/docs")
    print(f"Review UI: {url}")
    print(f"Trace Explorer: http://localhost:{settings.API_PORT}/traces")

    # Open browser automatically after the server starts
    threading.Timer(
        2.0,
        lambda: webbrowser.open(url)
    ).start()

    uvicorn.run(
        "api.server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--server":
            run_server()
        elif sys.argv[1] == "--demo":
            # Import and run demo
            from demo import run_demo
            run_demo()
        else:
            # Custom request
            request = " ".join(sys.argv[1:])
            run_task(request)
    else:
        # Default demo task
        run_task("Look up what LangGraph is used for, then write a 2-sentence summary of it.")
