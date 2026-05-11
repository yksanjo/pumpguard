"""Tests for SQLite memory layer."""

from __future__ import annotations

from pumpguard.memory import Memory


def test_record_and_check_token(memory: Memory) -> None:
    """Recording a token should make has_seen_token return True."""
    assert not memory.has_seen_token("test_mint_1")
    memory.record_token("test_mint_1", "TEST", "Test Token", "wallet1", 0.5)
    assert memory.has_seen_token("test_mint_1")


def test_idempotent_record(memory: Memory) -> None:
    """Recording the same token twice should not error."""
    memory.record_token("test_mint_2", "TEST2", "Test Token 2", "wallet2", 0.3)
    memory.record_token("test_mint_2", "TEST2", "Test Token 2", "wallet2", 0.3)
    assert memory.has_seen_token("test_mint_2")


def test_deployer_tracking(memory: Memory) -> None:
    """Deployer launch count should increment on each touch."""
    record = memory.deployer_record("wallet3")
    assert record is None

    memory.touch_deployer("wallet3")
    record = memory.deployer_record("wallet3")
    assert record is not None
    assert record["launch_count"] == 1
    assert record["rug_count"] == 0

    memory.touch_deployer("wallet3", is_rug=True)
    record = memory.deployer_record("wallet3")
    assert record["launch_count"] == 2
    assert record["rug_count"] == 1


def test_alert_recording(memory: Memory) -> None:
    """Alerts should be stored and retrievable."""
    aid = memory.record_alert("mint4", "ALRT", 0.8, "GREEN", "test alert")
    assert aid > 0

    alerts = memory.recent_alerts()
    assert len(alerts) == 1
    assert alerts[0]["mint"] == "mint4"
    assert alerts[0]["alert_level"] == "GREEN"
