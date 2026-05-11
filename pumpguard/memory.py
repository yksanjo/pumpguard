"""SQLite-backed memory: tokens seen, deployer history, alerts.

PumpGuard learns over time — deployer reputation persists across sessions.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens_seen (
    mint TEXT PRIMARY KEY,
    symbol TEXT,
    name TEXT,
    deployer TEXT,
    score REAL DEFAULT 0,
    deployed_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deployers (
    wallet TEXT PRIMARY KEY,
    rug_count INTEGER DEFAULT 0,
    launch_count INTEGER DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mint TEXT NOT NULL,
    symbol TEXT,
    score REAL NOT NULL,
    alert_level TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_tokens_deployer ON tokens_seen(deployer);
"""


class Memory:
    """Wraps the SQLite store. One per process is fine."""

    def __init__(self, db_path: str):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- tokens ---

    def record_token(
        self,
        mint: str,
        symbol: str,
        name: str,
        deployer: str,
        score: float,
        deployed_at: str | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT OR IGNORE INTO tokens_seen
                   (mint, symbol, name, deployer, score, deployed_at, first_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (mint, symbol, name, deployer, score,
                 deployed_at or self._now(), self._now()),
            )

    def has_seen_token(self, mint: str) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM tokens_seen WHERE mint = ?", (mint,)
            ).fetchone()
            return row is not None

    # --- deployers ---

    def touch_deployer(self, wallet: str, *, is_rug: bool = False) -> None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM deployers WHERE wallet = ?", (wallet,)
            ).fetchone()
            now = self._now()
            if row is None:
                c.execute(
                    """INSERT INTO deployers
                       (wallet, rug_count, launch_count, first_seen_at, last_seen_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (wallet, 1 if is_rug else 0, 1, now, now),
                )
            else:
                c.execute(
                    """UPDATE deployers
                       SET launch_count = launch_count + 1,
                           rug_count = rug_count + ?,
                           last_seen_at = ?
                       WHERE wallet = ?""",
                    (1 if is_rug else 0, now, wallet),
                )

    def deployer_record(self, wallet: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM deployers WHERE wallet = ?", (wallet,)
            ).fetchone()
            return dict(row) if row else None

    # --- alerts ---

    def record_alert(
        self,
        mint: str,
        symbol: str,
        score: float,
        alert_level: str,
        message: str,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO alerts
                   (mint, symbol, score, alert_level, message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (mint, symbol, score, alert_level, message, self._now()),
            )
            return cur.lastrowid

    def recent_alerts(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
