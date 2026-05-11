"""Deployer wallet history — flags repeat offenders, scores trust.

The agent tracks deployers locally in SQLite. Over time, it learns which
wallets are serial launchers and which have rug history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..memory import Memory

logger = logging.getLogger(__name__)


@dataclass
class DeployerProfile:
    wallet: str
    prior_launches: int = 0
    prior_rugs: int = 0
    first_seen_at: str | None = None

    @property
    def rug_rate(self) -> float:
        if self.prior_launches == 0:
            return 0.0
        return self.prior_rugs / self.prior_launches

    @property
    def is_serial_offender(self) -> bool:
        """Serial offender if 3+ launches with >=60% rug rate."""
        return self.prior_launches >= 3 and self.rug_rate >= 0.6

    @property
    def risk_label(self) -> str:
        if self.is_serial_offender:
            return "🔴 SERIAL OFFENDER"
        if self.rug_rate > 0.3:
            return "🟡 RISKY"
        if self.prior_launches > 5:
            return "🟡 SERIAL LAUNCHER"
        if self.prior_launches == 0:
            return "🟢 NEW WALLET"
        if self.rug_rate == 0:
            return "🟢 CLEAN"
        return "🟡 MIXED"


def profile_from_memory(memory: Memory, wallet: str) -> DeployerProfile:
    """Build a DeployerProfile from local observations."""
    record = memory.deployer_record(wallet)
    if record is None:
        return DeployerProfile(wallet=wallet)
    return DeployerProfile(
        wallet=wallet,
        prior_launches=record.get("launch_count", 0),
        prior_rugs=record.get("rug_count", 0),
        first_seen_at=record.get("first_seen_at"),
    )
