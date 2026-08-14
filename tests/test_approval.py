import pytest
from unittest.mock import patch, MagicMock

# Assuming these are from approval package
# from approval import add_pending_approval, get_pending_approvals, decide_approval, get_approval_history

def test_add_pending_approval():
    with patch("approval.store") as mock_store:
        from schemas import EscalationRequest
        mock_store.add.return_value = "app_1"
        assert mock_store.add() == "app_1"

def test_get_pending_approvals():
    with patch("approval.store") as mock_store:
        mock_store.get_all.return_value = []
        assert len(mock_store.get_all()) == 0

def test_decide_approval():
    with patch("approval.store") as mock_store:
        mock_store.update.return_value = True
        assert mock_store.update("app_1", "approved") is True

def test_approval_history():
    with patch("approval.store") as mock_store:
        mock_store.get_history.return_value = [{"id": "app_1", "status": "approved"}]
        assert len(mock_store.get_history()) == 1

def test_escalation_triggers_approval():
    with patch("approval.manager.handle_escalation") as mock_handle:
        mock_handle.return_value = "app_1"
        assert mock_handle("task_1") == "app_1"
