from typing import Optional
from .semantic import SemanticMemory

class MemoryRetrieval:
    """
    Retrieves and formats contextual memory to augment planning and specialized prompts.
    """
    def __init__(self, semantic_memory: SemanticMemory):
        self.memory = semantic_memory

    def augment_planning_prompt(self, request: str, user_id: str = "default") -> str:
        """
        Retrieves relevant past tasks, tools, and user preferences to build a context block.
        """
        context_parts = []

        # 1. User preferences
        prefs = self.memory.get_user_preferences(user_id=user_id)
        if prefs:
            prefs_str = "\n".join([f"- {p['preference']} (Category: {p.get('metadata', {}).get('category', 'general')})" for p in prefs])
            context_parts.append(f"### User Preferences:\n{prefs_str}")

        # 2. Similar past tasks
        similar_tasks = self.memory.retrieve_similar_tasks(query=request, n_results=3, user_id=user_id)
        if similar_tasks:
            tasks_str = "\n".join([
                f"- Task: {t['content']}\n  Outcome: {t.get('metadata', {}).get('outcome', 'unknown')} (Score: {t.get('metadata', {}).get('score', 0)})"
                for t in similar_tasks
            ])
            context_parts.append(f"### Similar Past Tasks:\n{tasks_str}")

        # 3. Tool recommendations
        tools = self.memory.get_tool_recommendations(task_description=request, n=3)
        if tools:
            tools_str = "\n".join([
                f"- Tool: {t.get('metadata', {}).get('tool_name', 'unknown')}\n  Context: {t['context']}"
                for t in tools
            ])
            context_parts.append(f"### Successful Tool Usage Patterns:\n{tools_str}")

        if not context_parts:
            return ""
            
        return "\n\n".join(["--- MEMORY CONTEXT ---"] + context_parts + ["----------------------\n"])

    def get_specialist_context(self, subtask_description: str, specialist_type: str) -> str:
        """
        Gets relevant facts and history for a specific specialist.
        """
        facts = self.memory.retrieve_relevant_facts(query=subtask_description, domain=specialist_type, n_results=3)
        
        if not facts:
            return ""
            
        facts_str = "\n".join([f"- {f['fact']}" for f in facts])
        return f"### Domain Context ({specialist_type}):\n{facts_str}\n"
