"""
Full demo scenario showcasing the complete agent hierarchy.

This runs a complex multi-specialist task:
1. Research: Search for top Python web frameworks
2. Data: Extract and structure the comparison data
3. Code: Analyze trends with Python code
4. Writing: Produce a comprehensive comparison summary
"""
import json
import time
from config import setup_logging, get_settings

def run_demo():
    setup_logging()
    settings = get_settings()
    
    if not settings.GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set.")
        return
    
    print("=" * 60)
    print("AGENT ORCHESTRATOR — FULL DEMO")
    print("=" * 60)
    
    from main import run_task
    
    # Demo 1: Simple research + writing
    print("\n--- Demo 1: Research + Writing ---")
    run_task("What are the key features of FastAPI? Write a brief summary.")
    
    print("\n" + "=" * 60)
    
    # Demo 2: Multi-specialist task
    print("\n--- Demo 2: Multi-Specialist Task ---")
    run_task(
        "Research the top 3 Python web frameworks (Django, Flask, FastAPI), "
        "compare their features and use cases, "
        "then write a recommendation for building a REST API."
    )
    
    print("\n" + "=" * 60)
    
    # Demo 3: Code specialist
    print("\n--- Demo 3: Code Execution ---")
    run_task(
        "Write Python code to calculate the first 20 Fibonacci numbers "
        "and display them in a formatted table, then write a brief explanation "
        "of the Fibonacci sequence."
    )
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    
    # Show memory stats
    try:
        from memory.semantic import SemanticMemory
        from memory.management import MemoryManager
        sm = SemanticMemory()
        mgr = MemoryManager(sm)
        dashboard = mgr.get_dashboard_data()
        print(f"\nMemory Stats: {json.dumps(dashboard, indent=2, default=str)}")
    except Exception as e:
        print(f"\nMemory stats unavailable: {e}")


if __name__ == "__main__":
    run_demo()
