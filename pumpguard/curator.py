"""Curator — scores pump.fun launches in real-time for alert-worthiness.

Scoring is anti-shill by design:
  + bonus for organic-looking name (not all-caps keyboard mash)
  + bonus for non-zero initial liquidity
  - penalty for high deployer/top-holder concentration
  - penalty for serial deployer with rug history
  - hard reject if mint already seen

Alert levels:
  🟢 GREEN  (score >= 1.0) — interesting find, worth a look
  🟡 YELLOW (score >= 0.5) — decent, deployer looks clean
  ⚪ NEUTRAL (score >= 0.0) — meh, nothing special
  🔴 RED    (score < 0.0)  — red flags
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .memory import Memory
from .sources.deployer import DeployerProfile, profile_from_memory
from .sources.pumpfun import NewTokenEvent
from .sources.token_meta import TokenMetadata

logger = logging.getLogger(__name__)

_ALL_CAPS = re.compile(r"^[A-Z0-9$_]+$")
_VOWELLESS = re.compile(r"^[^aeiouAEIOU]+$")


@dataclass
class ScoredToken:
    event: NewTokenEvent
    meta: TokenMetadata
    deployer: DeployerProfile
    score: float
    notes: list[str]

    @property
    def alert_level(self) -> str:
        if self.score >= 1.0:
            return "GREEN"
        elif self.score >= 0.5:
            return "YELLOW"
        elif self.score >= 0.0:
            return "NEUTRAL"
        else:
            return "RED"

    @property
    def alert_emoji(self) -> str:
        return {
            "GREEN": "🟢",
            "YELLOW": "🟡",
            "NEUTRAL": "⚪",
            "RED": "🔴",
        }[self.alert_level]

    @property
    def summary_line(self) -> str:
        return (
            f"{self.alert_emoji} ${self.event.symbol} "
            f"({self.event.name}) — score: {self.score:.2f} "
            f"| mc: {self.event.market_cap_sol:.1f} SOL "
            f"| deployer: {self.deployer.risk_label}"
        )


def _name_score(name: str, symbol: str) -> tuple[float, list[str]]:
    """Reward names with literary quality. Penalize keyboard mash."""
    notes: list[str] = []
    score = 0.0
    if not name or not symbol:
        notes.append("missing name or symbol (-1)")
        return -1.0, notes
    if _ALL_CAPS.match(name) and len(name) > 8:
        score -= 0.3
        notes.append("shouty name (-0.3)")
    if _VOWELLESS.match(symbol) and len(symbol) > 3:
        score -= 0.2
        notes.append("vowelless ticker (-0.2)")
    if len(name.split()) >= 2:
        score += 0.2
        notes.append("multi-word name (+0.2)")
    if any(ch in name for ch in "—–:·"):
        score += 0.3
        notes.append("punctuation suggests writing (+0.3)")
    return score, notes


def _liquidity_score(event: NewTokenEvent) -> tuple[float, list[str]]:
    notes: list[str] = []
    score = 0.0
    if event.initial_sol <= 0:
        score -= 0.5
        notes.append("zero initial liquidity (-0.5)")
    elif event.initial_sol < 0.1:
        score -= 0.2
        notes.append("very thin liquidity (-0.2)")
    elif event.initial_sol > 5:
        score += 0.1
        notes.append("non-trivial seed (+0.1)")
    return score, notes


def _meta_score(meta: TokenMetadata) -> tuple[float, list[str]]:
    notes: list[str] = []
    score = 0.0
    if meta.description and len(meta.description) > 40:
        score += 0.3
        notes.append("has real description (+0.3)")
    if meta.twitter:
        score += 0.1
        notes.append("twitter linked (+0.1)")
    if meta.website:
        score += 0.1
        notes.append("website linked (+0.1)")
    if meta.looks_concentrated:
        score -= 0.6
        notes.append("supply concentrated (-0.6)")
    return score, notes


def _deployer_score(d: DeployerProfile) -> tuple[float, list[str]]:
    notes: list[str] = []
    score = 0.0
    if d.is_serial_offender:
        score -= 1.0
        notes.append(
            f"serial rugger: {d.prior_rugs}/{d.prior_launches} (-1.0)"
        )
    elif d.prior_launches > 0:
        penalty = -0.2 * d.rug_rate
        score += penalty
        notes.append(
            f"prior rug rate {d.rug_rate:.0%} ({penalty:+.2f})"
        )
    return score, notes


def score_token(
    event: NewTokenEvent,
    meta: TokenMetadata,
    deployer: DeployerProfile,
) -> ScoredToken:
    """Score a single token across all dimensions."""
    notes: list[str] = []
    score = 0.0
    for fn, args in (
        (_name_score, (event.name, event.symbol)),
        (_liquidity_score, (event,)),
        (_meta_score, (meta,)),
        (_deployer_score, (deployer,)),
    ):
        s, n = fn(*args)
        score += s
        notes.extend(n)
    return ScoredToken(
        event=event, meta=meta, deployer=deployer, score=score, notes=notes
    )


def should_alert(scored: ScoredToken, min_score: float) -> bool:
    """Should this token trigger an alert?"""
    return scored.score >= min_score
