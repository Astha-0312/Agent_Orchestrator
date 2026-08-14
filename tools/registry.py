import time
import logging
from typing import Callable, Dict, List, Any, Optional
import datetime

logger = logging.getLogger("agent_orchestrator.tools")

class ToolSpec:
    def __init__(self, name: str, fn: Callable, description: str, parameters: Optional[Dict] = None):
        self.name = name
        self.fn = fn
        self.description = description
        self.parameters = parameters or {}

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
    
    def register(self, name: str, fn: Callable, description: str, parameters: Optional[Dict] = None) -> None:
        self._tools[name] = ToolSpec(name, fn, description, parameters)
        logger.debug(f"Registered tool: {name}")
    
    def invoke(self, name: str, args: Dict[str, Any]) -> dict:
        start_time = time.time()
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        result = ""
        error = None
        
        if name not in self._tools:
            error = f"Tool '{name}' not found in registry."
            logger.error(error)
        else:
            try:
                logger.info(f"Invoking tool '{name}' with args: {args}")
                tool_fn = self._tools[name].fn
                result = str(tool_fn(**args))
            except Exception as e:
                error = str(e)
                logger.error(f"Error invoking tool '{name}': {error}", exc_info=True)
                
        duration_ms = (time.time() - start_time) * 1000.0
        
        return {
            "tool_name": name,
            "args": args,
            "result": result,
            "duration_ms": duration_ms,
            "error": error,
            "timestamp": timestamp
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters
            }
            for spec in self._tools.values()
        ]
    
    def get_tool_descriptions(self) -> str:
        descriptions = []
        for tool in self.list_tools():
            desc = f"- {tool['name']}: {tool['description']}\n  Parameters: {tool['parameters']}"
            descriptions.append(desc)
        return "\n".join(descriptions)
    
    def has_tool(self, name: str) -> bool:
        return name in self._tools

# Global default registry
default_registry = ToolRegistry()
