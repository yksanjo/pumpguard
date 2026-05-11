"""Tests for config loading — defaults are load-bearing for safety."""

from __future__ import annotations

from pumpguard.config import Config, get_config


def test_defaults_are_safe() -> None:
    """Default config should have dry_run=True and no API keys set."""
    cfg = get_config()
    assert cfg.dry_run is True
    assert cfg.helius_api_key == ""
    assert cfg.telegram_bot_token == ""
    assert cfg.min_alert_score == 0.5


def test_default_db_path() -> None:
    """Default database path should be under home directory."""
    cfg = get_config()
    assert ".pumpguard" in cfg.database_path
    assert cfg.database_path.endswith(".sqlite")
