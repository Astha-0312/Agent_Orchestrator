"""
LangGraph state machine — full orchestration flow.

Flow: memory_retrieval -> supervisor -> specialist -> reviewer -> (next | retry | escalate | done) -> memory_write
"""
import logging
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END

from config import get_settings
from schemas import TaskPlan, SpecialistOutput, ReviewResult, EscalationRequest
from agents import (supervisor_plan, run_research_specialist, run_writing_specialist,
                    run_data_specialist, run_code_specialist, review_output)
from tracing.tracer import ExecutionTracer
from memory.working import RedisWorkingMemory

logger = logging.getLogger("agent_orchestrator.graph")


class AgentState(TypedDict):
    request: str
    plan: Optional[TaskPlan]
    current_subtask_index: int
    subtask_outputs: dict  # subtask_id -> output text
    retry_count: int
    reviewer_feedback: str  # feedback from reviewer for retry
    trace: List[dict]
    final_output: Optional[str]
    next_action: Optional[str]  # retry, next_subtask, done, escalate
    confidence: float
    escalation_requests: List[dict]
    total_cost_usd: float
    total_tokens: int
    memory_context: str  # injected by memory_retrieval_node
    tracer: Optional[Any]  # ExecutionTracer instance (not serializable)
    working_memory: Optional[Any]  # RedisWorkingMemory instance


def log_event(state: AgentState, event: str, detail: dict):
    """Append event to trace log and publish to working memory."""
    entry = {"event": event, "detail": detail}
    state["trace"].append(entry)
    
    wm = state.get("working_memory")
    if wm:
        try:
            wm.publish_event(event, detail)
        except Exception:
            pass


def _update_costs(state: AgentState, usage: dict):
    """Update running cost/token totals from LLM usage metadata."""
    state["total_cost_usd"] += usage.get("cost_usd", 0)
    state["total_tokens"] += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)


# ================ Nodes ================

def memory_retrieval_node(state: AgentState) -> AgentState:
    """Fetch relevant memories to augment supervisor planning."""
    logger.info("[memory_retrieval] fetching relevant memories...")
    
    tracer = state.get("tracer")
    span = None
    if tracer:
        span = tracer.start_span("memory_retrieval", span_type="memory_retrieval")
    
    try:
        from memory.semantic import SemanticMemory
        from memory.retrieval import MemoryRetrieval
        sm = SemanticMemory()
        retrieval = MemoryRetrieval(sm)
        context = retrieval.augment_planning_prompt(state["request"])
        state["memory_context"] = context
        if context:
            logger.info(f"[memory_retrieval] found relevant context ({len(context)} chars)")
        else:
            logger.info("[memory_retrieval] no relevant memories found")
        
        log_event(state, "memory_retrieved", {"context_length": len(context)})
    except Exception as e:
        logger.warning(f"[memory_retrieval] failed: {e}")
        state["memory_context"] = ""
    
    if tracer and span:
        tracer.end_span(span.span_id, status="success")
    
    return state


def supervisor_node(state: AgentState) -> AgentState:
    """Plan the task into subtasks."""
    logger.info("[supervisor] planning...")
    settings = get_settings()
    
    tracer = state.get("tracer")
    span = None
    if tracer:
        span = tracer.start_span("supervisor", span_type="node")
    
    plan, usage = supervisor_plan(state["request"], state.get("memory_context", ""))
    _update_costs(state, usage)
    
    state["plan"] = plan
    state["current_subtask_index"] = 0
    state["subtask_outputs"] = {}
    state["retry_count"] = 0
    state["confidence"] = plan.confidence
    state["reviewer_feedback"] = ""
    
    # Save plan to working memory
    wm = state.get("working_memory")
    if wm:
        try:
            wm.save_plan(plan.model_dump())
        except Exception:
            pass
    
    log_event(state, "plan_created", {
        "subtasks": [s.model_dump() for s in plan.subtasks],
        "confidence": plan.confidence,
        "cost_usd": usage.get("cost_usd", 0),
    })
    
    logger.info(f"[supervisor] {len(plan.subtasks)} subtasks, confidence={plan.confidence}")
    for i, st in enumerate(plan.subtasks):
        logger.info(f"  [{i}] id={st.id} specialist={st.specialist} depends_on={st.depends_on}")
    
    if tracer and span:
        tracer.end_span(span.span_id, 
                       input_tokens=usage.get("input_tokens", 0),
                       output_tokens=usage.get("output_tokens", 0),
                       cost=usage.get("cost_usd", 0))
    
    return state


def confidence_check_node(state: AgentState) -> AgentState:
    """Check if plan confidence is too low — escalate if so."""
    settings = get_settings()
    if state["confidence"] < settings.ESCALATION_CONFIDENCE_THRESHOLD:
        logger.warning(f"[confidence_check] low confidence {state['confidence']}, escalating")
        escalation = EscalationRequest(
            task_id=state.get("tracer", {}).task_id if state.get("tracer") else "",
            reason=f"Low plan confidence: {state['confidence']}",
            severity=4,
            context={"plan": state["plan"].model_dump() if state["plan"] else {}},
            suggested_action="Review and approve the execution plan before proceeding",
            approval_level="approve_plan",
        )
        state["escalation_requests"].append(escalation.model_dump())
        state["next_action"] = "escalate"
        log_event(state, "escalation_created", {"reason": escalation.reason})
    else:
        state["next_action"] = "proceed"
    
    return state


def specialist_node(state: AgentState) -> AgentState:
    """Execute the current subtask's specialist."""
    plan = state["plan"]
    idx = state["current_subtask_index"]
    subtask = plan.subtasks[idx]
    
    logger.info(f"[specialist:{subtask.specialist}] index {idx}/{len(plan.subtasks)-1}, "
                f"id={subtask.id}, retry={state['retry_count']}")
    
    tracer = state.get("tracer")
    span = None
    if tracer:
        span = tracer.start_span(f"specialist:{subtask.specialist}", 
                                span_type="node",
                                metadata={"subtask_id": subtask.id})
    
    # Build context from dependencies
    context = "\n\n".join(
        f"[{dep_id}]: {state['subtask_outputs'].get(dep_id, '')}"
        for dep_id in subtask.depends_on
    )
    
    feedback = state.get("reviewer_feedback", "") if state["retry_count"] > 0 else ""
    usage = {}
    
    if subtask.specialist == "research":
        result = run_research_specialist(subtask.id, subtask.description, context, feedback)
    elif subtask.specialist == "writing":
        result, usage = run_writing_specialist(subtask.id, subtask.description, context, feedback)
    elif subtask.specialist == "data":
        result = run_data_specialist(subtask.id, subtask.description, context, feedback)
    elif subtask.specialist == "code":
        result, usage = run_code_specialist(subtask.id, subtask.description, context, feedback)
    else:
        logger.error(f"Unknown specialist type: {subtask.specialist}")
        result = SpecialistOutput(
            subtask_id=subtask.id,
            specialist=subtask.specialist,
            output=f"Error: Unknown specialist type '{subtask.specialist}'",
        )
    
    if usage:
        _update_costs(state, usage)
    
    state["subtask_outputs"][subtask.id] = result.output
    
    # Save to working memory
    wm = state.get("working_memory")
    if wm:
        try:
            wm.save_subtask_output(subtask.id, result.output)
        except Exception:
            pass
    
    # Log tool calls to semantic memory
    for tc in result.tool_calls:
        try:
            from memory.semantic import SemanticMemory
            sm = SemanticMemory()
            sm.store_tool_usage(
                tc.tool_name, subtask.description,
                tc.error is None, tc.duration_ms
            )
        except Exception:
            pass
    
    log_event(state, "specialist_ran", {
        "subtask_id": subtask.id,
        "specialist": subtask.specialist,
        "output_preview": result.output[:300],
        "tool_calls": len(result.tool_calls),
    })
    
    if tracer and span:
        tracer.end_span(span.span_id,
                       input_tokens=usage.get("input_tokens", 0),
                       output_tokens=usage.get("output_tokens", 0),
                       cost=usage.get("cost_usd", 0))
    
    logger.info(f"[specialist:{subtask.specialist}] done")
    return state


def reviewer_node(state: AgentState) -> AgentState:
    """Review the current subtask output and decide next action."""
    settings = get_settings()
    plan = state["plan"]
    subtask = plan.subtasks[state["current_subtask_index"]]
    output = state["subtask_outputs"][subtask.id]
    
    logger.info(f"[reviewer] scoring subtask {subtask.id}...")
    
    tracer = state.get("tracer")
    span = None
    if tracer:
        span = tracer.start_span("reviewer", span_type="node",
                                metadata={"subtask_id": subtask.id})
    
    review, usage = review_output(subtask.id, subtask.description, output)
    _update_costs(state, usage)
    
    log_event(state, "reviewed", {
        "subtask_id": subtask.id,
        "score": review.score,
        "passed": review.passed,
        "feedback": review.feedback,
    })
    
    logger.info(f"[reviewer] score={review.score}, passed={review.passed}")
    
    # Decision logic
    if not review.passed and state["retry_count"] < settings.MAX_RETRIES_PER_SUBTASK:
        # Retry with feedback
        state["retry_count"] += 1
        state["reviewer_feedback"] = review.feedback
        state["next_action"] = "retry"
        logger.info(f"[reviewer] retrying subtask {subtask.id} (attempt {state['retry_count']})")
    elif not review.passed and review.score <= settings.ESCALATION_SCORE_THRESHOLD:
        # Escalate — score too low even after retries
        escalation = EscalationRequest(
            subtask_id=subtask.id,
            reason=f"Specialist failed after {state['retry_count']} retries. Score: {review.score}. Feedback: {review.feedback}",
            severity=review.score,
            context={
                "subtask": subtask.model_dump(),
                "output_preview": output[:500],
                "review": review.model_dump(),
            },
            suggested_action="Review specialist output and provide guidance or take over",
            approval_level="take_over",
        )
        state["escalation_requests"].append(escalation.model_dump())
        state["next_action"] = "escalate"
        logger.warning(f"[reviewer] escalating subtask {subtask.id}")
    else:
        # Pass — move to next subtask
        state["current_subtask_index"] += 1
        state["retry_count"] = 0
        state["reviewer_feedback"] = ""
        
        if state["current_subtask_index"] >= len(plan.subtasks):
            last_id = plan.subtasks[-1].id
            state["final_output"] = state["subtask_outputs"][last_id]
            state["next_action"] = "done"
            logger.info("[reviewer] all subtasks complete")
        else:
            state["next_action"] = "next_subtask"
            logger.info(f"[reviewer] advancing to index {state['current_subtask_index']}")
    
    if tracer and span:
        tracer.end_span(span.span_id,
                       input_tokens=usage.get("input_tokens", 0),
                       output_tokens=usage.get("output_tokens", 0),
                       cost=usage.get("cost_usd", 0))
    
    return state


def escalation_node(state: AgentState) -> AgentState:
    """Handle escalation — log and mark for human review."""
    logger.warning("[escalation] task requires human intervention")
    
    # In a full production system with LangGraph checkpointing,
    # this would use interrupt() to pause the graph.
    # For now, we log the escalation and continue.
    
    log_event(state, "escalation_triggered", {
        "escalations": state["escalation_requests"],
    })
    
    # Try to notify via approval queue
    try:
        from api.routes.approvals import add_pending_approval
        for esc in state["escalation_requests"]:
            add_pending_approval(
                state.get("tracer").task_id if state.get("tracer") else "unknown",
                esc
            )
    except Exception as e:
        logger.debug(f"Could not add to approval queue: {e}")
    
    # If the escalation was about the plan, skip to done
    # If about a subtask, advance past it
    if state.get("plan"):
        state["current_subtask_index"] += 1
        state["retry_count"] = 0
        if state["current_subtask_index"] >= len(state["plan"].subtasks):
            last_id = state["plan"].subtasks[-1].id
            state["final_output"] = state["subtask_outputs"].get(last_id, "Task escalated for human review.")
            state["next_action"] = "done"
        else:
            state["next_action"] = "next_subtask"
    else:
        state["next_action"] = "done"
        state["final_output"] = "Task escalated for human review due to low confidence."
    
    return state


def memory_write_node(state: AgentState) -> AgentState:
    """Store task outcome in long-term semantic memory."""
    logger.info("[memory_write] storing task outcome...")
    
    try:
        from memory.semantic import SemanticMemory
        sm = SemanticMemory()
        
        task_id = state.get("tracer").task_id if state.get("tracer") else "unknown"
        tools_used = set()
        for event in state["trace"]:
            if event["event"] == "specialist_ran":
                tools_used.add(event["detail"].get("specialist", ""))
        
        # Compute average score
        scores = [e["detail"]["score"] for e in state["trace"] if e["event"] == "reviewed"]
        avg_score = int(sum(scores) / len(scores)) if scores else 3
        
        sm.store_task_outcome(
            task_id=task_id,
            description=state["request"],
            outcome=state.get("final_output", "")[:1000],
            score=avg_score,
            tools_used=list(tools_used),
        )
        logger.info("[memory_write] outcome stored")
    except Exception as e:
        logger.warning(f"[memory_write] failed: {e}")
    
    # Save trace to storage
    try:
        from tracing.storage import TraceStorage
        tracer = state.get("tracer")
        if tracer:
            storage = TraceStorage()
            tree = tracer.to_tree()
            storage.save_trace(
                task_id=tracer.task_id,
                request=state["request"],
                trace_tree=tree,
                total_cost=state["total_cost_usd"],
                total_latency=tracer.total_latency_ms(),
                total_tokens=state["total_tokens"],
            )
            storage.save_spans(tracer.task_id, tracer.get_flat_spans())
            logger.info("[memory_write] trace saved")
    except Exception as e:
        logger.warning(f"[memory_write] trace save failed: {e}")
    
    log_event(state, "task_completed", {
        "total_cost_usd": state["total_cost_usd"],
        "total_tokens": state["total_tokens"],
    })
    
    return state


# ================ Routing ================

def route_after_confidence(state: AgentState) -> str:
    return state["next_action"]  # "proceed" or "escalate"


def route_after_reviewer(state: AgentState) -> str:
    return state["next_action"]  # "retry", "next_subtask", "done", "escalate"


def route_after_escalation(state: AgentState) -> str:
    return state["next_action"]  # "next_subtask" or "done"


# ================ Build Graph ================

def build_graph():
    """Build and compile the full orchestration graph."""
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("memory_retrieval", memory_retrieval_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("confidence_check", confidence_check_node)
    graph.add_node("specialist", specialist_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("memory_write", memory_write_node)
    
    # Set entry point
    graph.set_entry_point("memory_retrieval")
    
    # Fixed edges
    graph.add_edge("memory_retrieval", "supervisor")
    graph.add_edge("supervisor", "confidence_check")
    graph.add_edge("specialist", "reviewer")
    graph.add_edge("memory_write", END)
    
    # Conditional: after confidence check
    graph.add_conditional_edges(
        "confidence_check",
        route_after_confidence,
        {
            "proceed": "specialist",
            "escalate": "escalation",
        }
    )
    
    # Conditional: after reviewer
    graph.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "retry": "specialist",
            "next_subtask": "specialist",
            "done": "memory_write",
            "escalate": "escalation",
        }
    )
    
    # Conditional: after escalation
    graph.add_conditional_edges(
        "escalation",
        route_after_escalation,
        {
            "next_subtask": "specialist",
            "done": "memory_write",
        }
    )
    
    return graph.compile()
