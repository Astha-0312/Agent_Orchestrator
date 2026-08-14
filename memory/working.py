import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("agent_orchestrator.memory")

class RedisWorkingMemory:
    """
    Short-term working memory scoped to a single task.
    Stores data in Redis if available, otherwise falls back to an in-memory dictionary.
    """
    def __init__(self, task_id: str, redis_url: str = "redis://localhost:6379/0", ttl: int = 86400):
        self.task_id = task_id
        self.ttl = ttl
        self.prefix = f"task:{task_id}"
        
        # Fallback storage if Redis is unavailable
        self._fallback: Dict[str, Any] = {
            "plan": None,
            "outputs": {},
            "state": {},
            "errors": [],
            "events": []
        }
        self._redis = None
        
        try:
            import redis
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory fallback. Reason: {e}")
            self._redis = None

    def save_plan(self, plan_data: dict) -> None:
        """Stores the plan as JSON."""
        if self._redis:
            self._redis.setex(f"{self.prefix}:plan", self.ttl, json.dumps(plan_data))
        else:
            self._fallback["plan"] = plan_data

    def save_subtask_output(self, subtask_id: str, output: str) -> None:
        """Stores the output of a specific subtask."""
        if self._redis:
            self._redis.hset(f"{self.prefix}:outputs", subtask_id, output)
            self._redis.expire(f"{self.prefix}:outputs", self.ttl)
        else:
            self._fallback["outputs"][subtask_id] = output

    def get_subtask_output(self, subtask_id: str) -> Optional[str]:
        """Retrieves the output of a specific subtask."""
        if self._redis:
            return self._redis.hget(f"{self.prefix}:outputs", subtask_id)
        return self._fallback["outputs"].get(subtask_id)

    def get_all_outputs(self) -> Dict[str, str]:
        """Gets all subtask outputs for the current task."""
        if self._redis:
            return self._redis.hgetall(f"{self.prefix}:outputs")
        return dict(self._fallback["outputs"])

    def save_state(self, key: str, value: Any) -> None:
        """Stores generic state information."""
        if self._redis:
            self._redis.hset(f"{self.prefix}:state", key, json.dumps(value))
            self._redis.expire(f"{self.prefix}:state", self.ttl)
        else:
            self._fallback["state"][key] = value

    def get_state(self, key: str) -> Optional[Any]:
        """Retrieves generic state information."""
        if self._redis:
            val = self._redis.hget(f"{self.prefix}:state", key)
            return json.loads(val) if val else None
        return self._fallback["state"].get(key)

    def get_full_state(self) -> Dict[str, Any]:
        """Retrieves the complete state for the current task."""
        if self._redis:
            raw_state = self._redis.hgetall(f"{self.prefix}:state")
            return {k: json.loads(v) for k, v in raw_state.items()}
        return dict(self._fallback["state"])

    def log_error(self, error: dict) -> None:
        """Appends an error to the error list."""
        if self._redis:
            self._redis.rpush(f"{self.prefix}:errors", json.dumps(error))
            self._redis.expire(f"{self.prefix}:errors", self.ttl)
        else:
            self._fallback["errors"].append(error)

    def get_errors(self) -> List[dict]:
        """Gets all logged errors for the current task."""
        if self._redis:
            raw_errors = self._redis.lrange(f"{self.prefix}:errors", 0, -1)
            return [json.loads(e) for e in raw_errors]
        return list(self._fallback["errors"])

    def publish_event(self, event_type: str, data: dict) -> None:
        """Publishes an event to a Redis pubsub channel."""
        event = {"type": event_type, "data": data}
        if self._redis:
            self._redis.publish(f"{self.prefix}:events", json.dumps(event))
        else:
            self._fallback["events"].append(event)
            logger.info(f"Fallback Event Published: {event_type} - {data}")

    def cleanup(self) -> None:
        """Deletes all keys and data associated with the current task."""
        if self._redis:
            keys = self._redis.keys(f"{self.prefix}:*")
            if keys:
                self._redis.delete(*keys)
        else:
            self._fallback = {
                "plan": None,
                "outputs": {},
                "state": {},
                "errors": [],
                "events": []
            }
