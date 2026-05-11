"""Alert system — sends notifications when PumpGuard finds something interesting.

Supports:
  - Terminal output (always on)
  - Telegram bot (optional, via TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .curator import ScoredToken

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    mint: str
    symbol: str
    score: float
    level: str
    message: str


def _format_alert(scored: ScoredToken) -> str:
    """Format a scored token into a human-readable alert message."""
    lines = [
        f"{scored.alert_emoji}  PumpGuard Alert",
        f"",
        f"Token: ${scored.event.symbol} — {scored.event.name}",
        f"Mint:  {scored.event.mint}",
        f"Score: {scored.score:.2f} ({scored.alert_level})",
        f"MCap:  {scored.event.market_cap_sol:.2f} SOL",
        f"Liq:   {scored.event.initial_sol:.2f} SOL",
        f"",
        f"Deployer: {scored.deployer.risk_label}",
    ]
    if scored.deployer.prior_launches > 0:
        lines.append(
            f"  {scored.deployer.prior_launches} launches, "
            f"{scored.deployer.prior_rugs} rugs"
        )
    if scored.notes:
        lines.append(f"")
        lines.append("Notes:")
        for note in scored.notes:
            lines.append(f"  • {note}")
    lines.append(f"")
    lines.append(f"Solscan: https://solscan.io/token/{scored.event.mint}")
    return "\n".join(lines)


def _format_telegram(scored: ScoredToken) -> str:
    """Format a scored token for Telegram (shorter, emoji-rich)."""
    deployer_info = (
        f"Deployer: {scored.deployer.risk_label}"
        + (
            f" ({scored.deployer.prior_launches} launches, "
            f"{scored.deployer.prior_rugs} rugs)"
            if scored.deployer.prior_launches > 0
            else ""
        )
    )
    return (
        f"{scored.alert_emoji} <b>${scored.event.symbol}</b> — {scored.event.name}\n"
        f"Score: {scored.score:.2f} | MCap: {scored.event.market_cap_sol:.1f} SOL\n"
        f"{deployer_info}\n"
        f"<code>{scored.event.mint[:12]}...</code>\n"
        f"<a href='https://solscan.io/token/{scored.event.mint}'>Solscan</a>"
    )


async def send_telegram_alert(
    bot_token: str, chat_id: str, scored: ScoredToken
) -> bool:
    """Send an alert via Telegram. Returns True on success."""
    if not bot_token or not chat_id:
        return False
    text = _format_telegram(scored)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            resp.raise_for_status()
            logger.info("telegram alert sent for %s", scored.event.symbol)
            return True
        except Exception as e:
            logger.warning("telegram send failed: %s", e)
            return False


def print_alert(scored: ScoredToken) -> None:
    """Print a formatted alert to the terminal."""
    print("\n" + "=" * 60)
    print(_format_alert(scored))
    print("=" * 60 + "\n")
