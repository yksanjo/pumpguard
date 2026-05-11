"""Configuration — env-var loader with sensible defaults.

PumpGuard is designed to work out of the box with zero configuration.
All API keys are optional. Without them, scoring uses only on-chain data
available through the PumpPortal WebSocket.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


def _default_db_path() -> str:
    home = Path.home()
    return str(home / ".pumpguard" / "pumpguard.sqlite")


@dataclass
class Config:
    # Data sources
    helius_api_key: str = ""
    bitquery_api_key: str = ""

    # Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Runtime
    database_path: str = field(default_factory=_default_db_path)
    log_level: str = "INFO"
    dry_run: bool = True

    # WebSocket
    pump_portal_ws_url: str = "wss://pumpportal.fun/api/data"

    # Scoring defaults
    min_alert_score: float = 0.5


def get_config() -> Config:
    """Load config from environment variables."""
    return Config(
        helius_api_key=_env_str("HELIUS_API_KEY"),
        bitquery_api_key=_env_str("BITQUERY_API_KEY"),
        telegram_bot_token=_env_str("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_env_str("TELEGRAM_CHAT_ID"),
        database_path=_env_str("DATABASE_PATH", _default_db_path()),
        log_level=_env_str("LOG_LEVEL", "INFO"),
        dry_run=_env_bool("DRY_RUN", True),
        min_alert_score=_env_float("MIN_ALERT_SCORE", 0.5),
    )
