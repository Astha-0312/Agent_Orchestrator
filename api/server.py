from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import logging

logger = logging.getLogger("agent_orchestrator.api")

# Import routes
from api.routes import tasks, approvals, memory, traces

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize connections
    logger.info("Starting Agent Orchestrator API")
    yield
    # Shutdown: cleanup
    logger.info("Shutting down Agent Orchestrator API")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Orchestrator API",
        description="Multi-agent orchestration system with memory, human-in-the-loop, and observability",
        version="1.0.0",
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
    app.include_router(approvals.router, prefix="/api/v1", tags=["Approvals"])
    app.include_router(memory.router, prefix="/api/v1", tags=["Memory"])
    app.include_router(traces.router, prefix="/api/v1", tags=["Traces"])
    
    # Serve frontend static files if they exist
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.exists(os.path.join(frontend_dir, "review-ui")):
        app.mount("/review", StaticFiles(directory=os.path.join(frontend_dir, "review-ui"), html=True), name="review-ui")
    if os.path.exists(os.path.join(frontend_dir, "trace-explorer")):
        app.mount("/traces", StaticFiles(directory=os.path.join(frontend_dir, "trace-explorer"), html=True), name="trace-explorer")
    
    from fastapi.responses import RedirectResponse


    @app.get("/")
    async def root():
      return RedirectResponse(url="/review/")
    
    @app.get("/health")
    def health():
        return {"status": "healthy"}
    
    return app

app = create_app()
