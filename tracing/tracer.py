import time
import uuid
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any

logger = logging.getLogger("agent_orchestrator.tracing")

@dataclass
class TraceSpan:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: Optional[str] = None
    node_name: str = ""
    span_type: str = "node"  # node, llm_call, tool_call, memory_retrieval, escalation
    start_time: float = 0.0
    end_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    status: str = "running"  # running, success, error, skipped
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['TraceSpan'] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def latency_ms(self) -> float:
        if self.end_time and self.start_time:
            return round((self.end_time - self.start_time) * 1000, 2)
        return 0.0
    
    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "node_name": self.node_name,
            "span_type": self.span_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "status": self.status,
            "metadata": self.metadata,
            "error": self.error,
            "children": [c.to_dict() for c in self.children],
        }


class ExecutionTracer:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.root_span: Optional[TraceSpan] = None
        self.spans: Dict[str, TraceSpan] = {}
        self._span_stack: List[str] = []
    
    def start_span(self, name: str, parent_id: Optional[str] = None, 
                   span_type: str = "node", metadata: Optional[Dict] = None) -> TraceSpan:
        if parent_id is None and self._span_stack:
            parent_id = self._span_stack[-1]
            
        span = TraceSpan(
            node_name=name,
            parent_id=parent_id,
            span_type=span_type,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        self.spans[span.span_id] = span
        
        if parent_id and parent_id in self.spans:
            self.spans[parent_id].children.append(span)
        elif not self.root_span:
            self.root_span = span
            
        self._span_stack.append(span.span_id)
        return span
    
    def end_span(self, span_id: str, input_tokens: int = 0, output_tokens: int = 0,
                 cost: float = 0.0, status: str = "success", 
                 metadata: Optional[Dict] = None, error: Optional[str] = None) -> TraceSpan:
        if span_id not in self.spans:
            logger.warning(f"Span {span_id} not found to end.")
            return TraceSpan(span_id=span_id, status="error", error="not found")
            
        span = self.spans[span_id]
        span.end_time = time.time()
        span.input_tokens = input_tokens
        span.output_tokens = output_tokens
        span.cost_usd = cost
        span.status = status
        span.error = error
        if metadata:
            span.metadata.update(metadata)
            
        if self._span_stack and self._span_stack[-1] == span_id:
            self._span_stack.pop()
        elif span_id in self._span_stack:
            self._span_stack.remove(span_id)
            
        return span
    
    def current_span_id(self) -> Optional[str]:
        return self._span_stack[-1] if self._span_stack else None
    
    def to_tree(self) -> dict:
        if self.root_span:
            return {
                "task_id": self.task_id,
                "root": self.root_span.to_dict(),
                "summary": self.get_summary()
            }
        return {"task_id": self.task_id, "root": None, "summary": {}}
    
    def get_summary(self) -> dict:
        return {
            "total_spans": len(self.spans),
            "total_cost_usd": self.total_cost(),
            "total_latency_ms": self.total_latency_ms(),
            "total_input_tokens": sum(s.input_tokens for s in self.spans.values()),
            "total_output_tokens": sum(s.output_tokens for s in self.spans.values()),
            "error_count": sum(1 for s in self.spans.values() if s.status == "error"),
        }
    
    def total_cost(self) -> float:
        return round(sum(s.cost_usd for s in self.spans.values()), 6)
    
    def total_latency_ms(self) -> float:
        if self.root_span:
            return self.root_span.latency_ms
        return 0.0
    
    def get_flat_spans(self) -> List[dict]:
        return [s.to_dict() for s in self.spans.values()]
