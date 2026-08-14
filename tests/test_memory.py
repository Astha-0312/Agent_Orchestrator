import pytest
from unittest.mock import patch, MagicMock
from memory import RedisWorkingMemory, SemanticMemory, MemoryRetrieval, MemoryManager

def test_working_memory_fallback():
    with patch("redis.Redis") as mock_redis:
        mock_redis.side_effect = ConnectionError()
        wm = RedisWorkingMemory()
        assert wm.use_fallback is True

def test_working_memory_save_get_plan():
    wm = RedisWorkingMemory()
    wm.save_plan("t1", {"subtasks": []})
    assert wm.get_plan("t1") == {"subtasks": []}

def test_working_memory_save_get_output():
    wm = RedisWorkingMemory()
    wm.save_output("t1", "s1", "done")
    assert wm.get_output("t1", "s1") == "done"

def test_working_memory_publish_event():
    wm = RedisWorkingMemory()
    wm.publish_event("t1", "update")
    # assert event published internally or via mock

def test_semantic_memory_store_retrieve():
    with patch("chromadb.Client") as mock_chroma:
        sm = SemanticMemory()
        sm.store("doc1", "content")
        sm.retrieve("query")
        assert mock_chroma.called

def test_semantic_memory_fallback():
    with patch("chromadb.Client", side_effect=Exception):
        sm = SemanticMemory()
        assert sm.use_fallback is True

def test_memory_retrieval_augment_prompt():
    mr = MemoryRetrieval()
    with patch.object(mr, "get_relevant_context", return_value=["ctx"]):
        prompt = mr.augment_prompt("prompt")
        assert "ctx" in prompt

def test_memory_manager_importance_scoring():
    mm = MemoryManager()
    with patch("agents.call_llm_json", return_value=({"importance": 0.8}, {})):
        score = mm.score_importance("content")
        assert score == 0.8

def test_memory_manager_dashboard():
    mm = MemoryManager()
    stats = mm.get_dashboard_stats()
    assert isinstance(stats, dict)
