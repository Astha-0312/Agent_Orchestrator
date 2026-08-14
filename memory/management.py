import time
import logging
from typing import List, Dict, Any, Optional

from .semantic import SemanticMemory

logger = logging.getLogger("agent_orchestrator.memory")

class MemoryManager:
    """
    Handles memory lifecycle management, cleanup, scoring, and analytics.
    """
    def __init__(self, semantic_memory: SemanticMemory, working_memory_class=None):
        self.semantic = semantic_memory
        self.working_memory_class = working_memory_class

    def score_importance(self, content: str, metadata: dict) -> float:
        """
        Scores a memory's importance from 0.0 to 1.0 using heuristics.
        """
        score = 0.5
        
        # Recency bump (newer = higher, up to 30 days)
        timestamp = metadata.get("timestamp", time.time())
        age_days = (time.time() - timestamp) / (86400)
        if age_days < 7:
            score += 0.2
        elif age_days < 30:
            score += 0.1
            
        # Outcome quality (high score = higher)
        outcome_score = metadata.get("score", 5)
        if outcome_score > 8:
            score += 0.2
        elif outcome_score < 4:
            score -= 0.2
            
        # Task complexity based on tools used
        tools_str = metadata.get("tools_used", "")
        if tools_str:
            num_tools = len(tools_str.split(","))
            if num_tools > 3:
                score += 0.1
                
        return max(0.0, min(1.0, score))

    def consolidate(self) -> int:
        """
        Merge very similar memories and update importance scores.
        For now, this is a placeholder implementation returning 0.
        """
        logger.info("Memory consolidation triggered.")
        if self.semantic._fallback_mode:
            return 0
            
        # To implement fully:
        # 1. Retrieve all task_outcomes
        # 2. Re-score via self.score_importance()
        # 3. Detect overlaps and merge/delete
        
        return 0

    def expire_old(self, max_age_days: int = 30, min_importance: float = 0.3) -> int:
        """
        Removes low-importance memories older than the given max age.
        """
        logger.info(f"Expiring memories older than {max_age_days} days with score < {min_importance}.")
        if self.semantic._fallback_mode or not self.semantic.task_outcomes:
            return 0
            
        expired_count = 0
        try:
            # Note: ChromaDB doesn't natively support inequality filtering on metadata values effectively 
            # for all setups, so we would typically pull all and filter, or use an external index.
            # Here we mock the behavior for the interface completeness.
            all_memories = self.semantic.task_outcomes.get()
            if all_memories and all_memories.get("ids"):
                ids_to_delete = []
                for i, metadata in enumerate(all_memories.get("metadatas", [])):
                    if metadata:
                        timestamp = metadata.get("timestamp", time.time())
                        age_days = (time.time() - timestamp) / 86400
                        content = all_memories["documents"][i] if all_memories.get("documents") else ""
                        score = self.score_importance(content, metadata)
                        
                        if age_days > max_age_days and score < min_importance:
                            ids_to_delete.append(all_memories["ids"][i])
                            
                if ids_to_delete:
                    self.semantic.task_outcomes.delete(ids=ids_to_delete)
                    expired_count = len(ids_to_delete)
        except Exception as e:
            logger.error(f"Failed to expire old memories: {e}")
            
        return expired_count

    def get_dashboard_data(self, user_id: str = "default") -> Dict:
        """
        Returns memory statistics for a user dashboard.
        """
        stats = {
            "total_memories": 0,
            "by_collection": {
                "task_outcomes": 0,
                "tool_usage": 0,
                "domain_facts": 0,
                "user_preferences": 0
            },
            "avg_importance": 0.0,
            "status": "active" if not self.semantic._fallback_mode else "degraded (fallback)"
        }
        
        if self.semantic._fallback_mode:
            return stats
            
        try:
            if self.semantic.task_outcomes:
                outcomes = self.semantic.task_outcomes.get(where={"user_id": user_id})
                stats["by_collection"]["task_outcomes"] = len(outcomes["ids"]) if outcomes else 0
                
            if self.semantic.user_preferences:
                prefs = self.semantic.user_preferences.get(where={"user_id": user_id})
                stats["by_collection"]["user_preferences"] = len(prefs["ids"]) if prefs else 0
                
            stats["total_memories"] = sum(stats["by_collection"].values())
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            
        return stats

    def delete_memory(self, memory_id: str, collection: str = "task_outcomes") -> bool:
        """
        Deletes a specific memory by ID from the specified collection.
        """
        if self.semantic._fallback_mode:
            return False
            
        try:
            target_collection = getattr(self.semantic, collection, None)
            if target_collection:
                target_collection.delete(ids=[memory_id])
                return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id} from {collection}: {e}")
            
        return False
