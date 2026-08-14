"""
Agent logic: Supervisor, Specialists (research, writing, data, code), Reviewer.

Each function is stateless — takes inputs, calls Groq, returns a validated Pydantic object.
All flow control lives in graph.py.
"""
import os
import json
import logging
from typing import Tuple, Dict, Any, Optional
from groq import Groq
from config import get_settings, calculate_cost
from schemas import TaskPlan, SpecialistOutput, ReviewResult, EscalationRequest, ToolCall
from tools import default_registry

logger = logging.getLogger("agent_orchestrator.agents")


def _get_client():
    """Lazy Groq client initialization."""
    settings = get_settings()
    return Groq(api_key=settings.GROQ_API_KEY)


def call_llm_json(system_prompt: str, user_prompt: str, model: str = None) -> Tuple[dict, dict]:
    """Calls Groq with JSON mode. Returns (parsed_dict, usage_metadata).
    usage_metadata contains: model, input_tokens, output_tokens, cost_usd, latency_ms"""
    import time
    settings = get_settings()
    model = model or settings.MODEL_NAME
    client = _get_client()
    
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        latency = (time.time() - start) * 1000
        
        content = response.choices[0].message.content
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = calculate_cost(model, input_tokens, output_tokens)
        
        usage_metadata = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "latency_ms": round(latency, 2),
        }
        
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"JSON parse error, attempting to extract JSON from response")
            # Try to find JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                parsed = json.loads(content[start_idx:end_idx])
            else:
                raise
        
        return parsed, usage_metadata
        
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.error(f"LLM call failed: {e}")
        raise


def call_llm_text(system_prompt: str, user_prompt: str, model: str = None) -> Tuple[str, dict]:
    """Calls Groq for plain text. Returns (text, usage_metadata)."""
    import time
    settings = get_settings()
    model = model or settings.MODEL_NAME
    client = _get_client()
    
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    latency = (time.time() - start) * 1000
    
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    cost = calculate_cost(model, input_tokens, output_tokens)
    
    usage_metadata = {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "latency_ms": round(latency, 2),
    }
    
    return response.choices[0].message.content.strip(), usage_metadata


# ================ Supervisor ================

SUPERVISOR_SYSTEM_PROMPT = """You are a task planning supervisor. Given a user request, break it \
into an ordered list of subtasks. Each subtask must be assigned to exactly one specialist:

- "research": looks things up using web search
- "writing": drafts/synthesizes text based on prior subtask outputs
- "data": extracts, analyzes, or queries structured data (databases, APIs)
- "code": writes and executes code for computation, analysis, or automation

Available tools: {tool_descriptions}

Respond ONLY with JSON matching this exact shape:
{{
  "subtasks": [
    {{"id": "subtask_1", "specialist": "research", "description": "...", "depends_on": [], "required_tools": ["web_search"]}},
    {{"id": "subtask_2", "specialist": "writing", "description": "...", "depends_on": ["subtask_1"], "required_tools": []}}
  ],
  "confidence": 0.85
}}

Keep plans short — 2 to 5 subtasks. A simple request should produce a simple plan.
Set confidence between 0.0 (unsure) and 1.0 (very confident).
If the request is ambiguous or you're unsure how to plan it, set confidence low.
"""


def supervisor_plan(request: str, memory_context: str = "") -> Tuple[TaskPlan, dict]:
    """Generate a task plan. Returns (plan, usage_metadata)."""
    settings = get_settings()
    tool_descriptions = default_registry.get_tool_descriptions()
    
    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)
    
    user_prompt = f"User request: {request}"
    if memory_context:
        user_prompt = f"Relevant context from past tasks:\n{memory_context}\n\n{user_prompt}"
    
    raw, usage = call_llm_json(system_prompt, user_prompt, model=settings.SUPERVISOR_MODEL)
    plan = TaskPlan(**raw)
    return plan, usage


# ================ Specialists ================

def run_research_specialist(subtask_id: str, description: str, 
                            context: str = "", feedback: str = "") -> SpecialistOutput:
    """Research specialist using web search tool."""
    search_query = description
    if feedback:
        search_query = f"{description} (Previous attempt feedback: {feedback})"
    
    tool_calls = []
    result = default_registry.invoke("web_search", {"query": search_query})
    tool_calls.append(ToolCall(**result))
    
    output = result["result"] if not result.get("error") else f"Search error: {result['error']}"
    
    return SpecialistOutput(
        subtask_id=subtask_id,
        specialist="research",
        output=output,
        raw_data=output,
        tool_calls=tool_calls,
    )


def run_writing_specialist(subtask_id: str, description: str, 
                           context: str = "", feedback: str = "") -> Tuple[SpecialistOutput, dict]:
    """Writing specialist using LLM."""
    system_prompt = (
        "You are a writing specialist. Use the provided context to complete the task. "
        "Be concise and factual. Do not invent information not present in the context."
    )
    
    user_prompt = f"Task: {description}"
    if context:
        user_prompt += f"\n\nContext:\n{context}"
    if feedback:
        user_prompt += f"\n\nPrevious attempt feedback (please address this):\n{feedback}"
    
    text, usage = call_llm_text(system_prompt, user_prompt)
    
    output = SpecialistOutput(
        subtask_id=subtask_id,
        specialist="writing",
        output=text,
    )
    return output, usage


def run_data_specialist(subtask_id: str, description: str, 
                        context: str = "", feedback: str = "") -> SpecialistOutput:
    """Data specialist using API calls and DB queries."""
    tool_calls = []
    results = []
    
    # Try API call first if description mentions URL/API
    if any(word in description.lower() for word in ["api", "http", "url", "endpoint", "fetch"]):
        # Extract URL from description or use as search context
        result = default_registry.invoke("api_get", {"url": description})
        tool_calls.append(ToolCall(**result))
        results.append(result["result"])
    
    # Try DB query if description mentions data/query/database
    if any(word in description.lower() for word in ["query", "database", "sql", "table", "data"]):
        # Generate a simple query from description
        query_prompt = f"Based on this task: {description}\nContext: {context}\nGenerate a simple SQL SELECT query."
        try:
            sql_text, _ = call_llm_text(
                "You are a SQL expert. Output ONLY a valid SELECT SQL query, nothing else.",
                query_prompt
            )
            result = default_registry.invoke("db_query", {"query": sql_text})
            tool_calls.append(ToolCall(**result))
            results.append(result["result"])
        except Exception as e:
            results.append(f"DB query generation failed: {e}")
    
    # If no specific tool matched, do web search as fallback
    if not results:
        result = default_registry.invoke("web_search", {"query": description})
        tool_calls.append(ToolCall(**result))
        results.append(result["result"])
    
    combined = "\n\n".join(results)
    return SpecialistOutput(
        subtask_id=subtask_id,
        specialist="data",
        output=combined,
        raw_data=combined,
        tool_calls=tool_calls,
    )


def run_code_specialist(subtask_id: str, description: str, 
                        context: str = "", feedback: str = "") -> Tuple[SpecialistOutput, dict]:
    """Code specialist: generates and executes Python code."""
    system_prompt = (
        "You are a code specialist. Write Python code to accomplish the task. "
        "Output ONLY the Python code, no markdown, no explanation. "
        "The code should print its results to stdout. "
        "Do not use any external libraries that aren't in the standard library, "
        "except: requests, json, csv, math, statistics."
    )
    
    user_prompt = f"Task: {description}"
    if context:
        user_prompt += f"\n\nAvailable data/context:\n{context}"
    if feedback:
        user_prompt += f"\n\nPrevious attempt feedback:\n{feedback}"
    
    code, usage = call_llm_text(system_prompt, user_prompt)
    
    # Clean up code (remove markdown fences if present)
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    
    # Execute the code
    tool_calls = []
    exec_result = default_registry.invoke("execute_python", {"code": code})
    tool_calls.append(ToolCall(**exec_result))
    
    output = exec_result["result"] if not exec_result.get("error") else f"Code execution error: {exec_result['error']}\nCode:\n{code}"
    
    return SpecialistOutput(
        subtask_id=subtask_id,
        specialist="code",
        output=output,
        raw_data=code,
        tool_calls=tool_calls,
    ), usage


# ================ Reviewer ================

REVIEWER_SYSTEM_PROMPT = """You are a reviewer checking whether a specialist's output actually \
satisfies its assigned subtask. Respond ONLY with JSON:
{{"score": <1-5>, "feedback": "...", "passed": <true/false>}}

score 1-2 = fails the task, 3 = partially satisfies, 4-5 = fully satisfies.
passed should be true only if score >= 3.
Be specific in feedback — explain what's missing or what could be improved.
"""


def review_output(subtask_id: str, subtask_description: str, 
                  specialist_output: str) -> Tuple[ReviewResult, dict]:
    """Review a specialist's output. Returns (review, usage_metadata)."""
    user_prompt = f"Subtask: {subtask_description}\n\nSpecialist output:\n{specialist_output}"
    raw, usage = call_llm_json(REVIEWER_SYSTEM_PROMPT, user_prompt)
    review = ReviewResult(subtask_id=subtask_id, **raw)
    return review, usage
