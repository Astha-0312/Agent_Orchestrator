import logging
import uuid
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("agent_orchestrator.memory")

class SemanticMemory:
    """
    Long-term semantic memory using ChromaDB.
    Handles gracefully if ChromaDB is unavailable by falling back to a no-op mode.
    """
    def __init__(self, path: str = "./chromadb_data"):
        self._fallback_mode = False
        self.client = None
        
        # Collection references
        self.task_outcomes = None
        self.tool_usage = None
        self.domain_facts = None
        self.user_preferences = None
        
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=path)
            self.task_outcomes = self.client.get_or_create_collection("task_outcomes")
            self.tool_usage = self.client.get_or_create_collection("tool_usage")
            self.domain_facts = self.client.get_or_create_collection("domain_facts")
            self.user_preferences = self.client.get_or_create_collection("user_preferences")
        except Exception as e:
            logger.warning(f"ChromaDB unavailable, using no-op fallback. Reason: {e}")
            self._fallback_mode = True

    def store_task_outcome(self, task_id: str, description: str, outcome: str, 
                           score: int, tools_used: List[str], user_id: str = "default") -> None:
        if self._fallback_mode or not self.task_outcomes:
            return
            
        doc_id = f"{task_id}_{uuid.uuid4().hex[:8]}"
        metadata = {
            "task_id": task_id,
            "outcome": outcome,
            "score": score,
            "tools_used": ",".join(tools_used),
            "user_id": user_id,
            "timestamp": time.time()
        }
        self.task_outcomes.add(
            ids=[doc_id],
            documents=[description],
            metadatas=[metadata]
        )

    def retrieve_similar_tasks(self, query: str, n_results: int = 5, 
                               user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self._fallback_mode or not self.task_outcomes:
            return []
            
        where_clause = {"user_id": user_id} if user_id else None
        
        results = self.task_outcomes.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        formatted_results = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            for idx in range(len(results["documents"][0])):
                formatted_results.append({
                    "id": results["ids"][0][idx],
                    "content": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx] if results.get("metadatas") else {},
                    "distance": results["distances"][0][idx] if results.get("distances") else 0.0
                })
        return formatted_results

    def store_tool_usage(self, tool_name: str, context: str, 
                         success: bool, duration_ms: float) -> None:
        if self._fallback_mode or not self.tool_usage:
            return
            
        doc_id = f"{tool_name}_{uuid.uuid4().hex[:8]}"
        metadata = {
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "timestamp": time.time()
        }
        self.tool_usage.add(
            ids=[doc_id],
            documents=[context],
            metadatas=[metadata]
        )

    def get_tool_recommendations(self, task_description: str, n: int = 3) -> List[Dict]:
        if self._fallback_mode or not self.tool_usage:
            return []
            
        results = self.tool_usage.query(
            query_texts=[task_description],
            n_results=n,
            where={"success": True}
        )
        
        recommendations = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            for idx in range(len(results["documents"][0])):
                recommendations.append({
                    "id": results["ids"][0][idx],
                    "context": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx] if results.get("metadatas") else {}
                })
        return recommendations

    def store_domain_fact(self, fact_id: str, fact: str, 
                          domain: str, importance: float = 0.5) -> None:
        if self._fallback_mode or not self.domain_facts:
            return
            
        metadata = {
            "domain": domain,
            "importance": importance,
            "timestamp": time.time()
        }
        self.domain_facts.add(
            ids=[fact_id],
            documents=[fact],
            metadatas=[metadata]
        )

    def retrieve_relevant_facts(self, query: str, domain: Optional[str] = None, 
                                n_results: int = 5) -> List[Dict]:
        if self._fallback_mode or not self.domain_facts:
            return []
            
        where_clause = {"domain": domain} if domain else None
        
        results = self.domain_facts.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        facts = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            for idx in range(len(results["documents"][0])):
                facts.append({
                    "id": results["ids"][0][idx],
                    "fact": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx] if results.get("metadatas") else {}
                })
        return facts

    def store_user_preference(self, user_id: str, preference: str, category: str) -> None:
        if self._fallback_mode or not self.user_preferences:
            return
            
        doc_id = f"{user_id}_{category}_{uuid.uuid4().hex[:8]}"
        metadata = {
            "user_id": user_id,
            "category": category,
            "timestamp": time.time()
        }
        self.user_preferences.add(
            ids=[doc_id],
            documents=[preference],
            metadatas=[metadata]
        )

    def get_user_preferences(self, user_id: str) -> List[Dict]:
        if self._fallback_mode or not self.user_preferences:
            return []
            
        # For simplicity, we get all elements for a user. In a real scenario, this might need pagination
        # or querying without text based purely on where clause.
        results = self.user_preferences.get(
            where={"user_id": user_id}
        )
        
        prefs = []
        if results and results.get("documents"):
            for idx in range(len(results["documents"])):
                prefs.append({
                    "id": results["ids"][idx],
                    "preference": results["documents"][idx],
                    "metadata": results["metadatas"][idx] if results.get("metadatas") else {}
                })
        return prefs

    def delete_user_data(self, user_id: str) -> int:
        """Deletes all data for a user across all collections."""
        if self._fallback_mode:
            return 0
            
        deleted_count = 0
        try:
            # Delete from task_outcomes
            outcomes = self.task_outcomes.get(where={"user_id": user_id})
            if outcomes and outcomes.get("ids"):
                self.task_outcomes.delete(ids=outcomes["ids"])
                deleted_count += len(outcomes["ids"])
                
            # Delete from user_preferences
            prefs = self.user_preferences.get(where={"user_id": user_id})
            if prefs and prefs.get("ids"):
                self.user_preferences.delete(ids=prefs["ids"])
                deleted_count += len(prefs["ids"])
        except Exception as e:
            logger.error(f"Failed to delete user data for {user_id}: {e}")
            
        return deleted_count
