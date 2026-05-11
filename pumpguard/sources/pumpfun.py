"""PumpPortal WebSocket adapter — streams new pump.fun token deploys in real time.

Connects to the free PumpPortal WebSocket at wss://pumpportal.fun/api/data
and subscribes to the `subscribeNewToken` channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

import websockets

logger = logging.getLogger(__name__)


@dataclass
class NewTokenEvent:
    mint: str
    symbol: str
    name: str
    deployer: str
    pool: str
    initial_sol: float
    market_cap_sol: float
    uri: str | None = None
    received_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    raw: dict = field(default_factory=dict)


def _parse(payload: dict) -> NewTokenEvent | None:
    """Parse a PumpPortal new-token payload. Defensive against key drift."""
    try:
        return NewTokenEvent(
            mint=payload["mint"],
            symbol=payload.get("symbol", ""),
            name=payload.get("name", ""),
            deployer=payload.get("traderPublicKey")
            or payload.get("creator")
            or "",
            pool=payload.get("pool", ""),
            initial_sol=float(payload.get("solAmount", 0) or 0),
            market_cap_sol=float(payload.get("marketCapSol", 0) or 0),
            uri=payload.get("uri"),
            raw=payload,
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("dropping malformed payload: %s — %s", e, payload)
        return None


async def stream_new_tokens(
    ws_url: str,
    *,
    max_events: int | None = None,
    timeout: float = 60.0,
) -> AsyncIterator[NewTokenEvent]:
    """Yield NewTokenEvent values as they arrive from PumpPortal.

    Args:
        ws_url: PumpPortal WebSocket endpoint.
        max_events: stop after N events (None = stream forever).
        timeout: per-message recv timeout in seconds.
    """
    sent = 0
    async with websockets.connect(ws_url, ping_interval=20) as ws:
        await ws.send(json.dumps({"method": "subscribeNewToken"}))
        logger.info("subscribed to new-token stream at %s", ws_url)

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.debug("recv timeout — sending ping")
                await ws.ping()
                continue

            try:
                payload = json.loads(msg)
            except json.JSONDecodeError:
                logger.warning("non-JSON message: %s", msg[:200])
                continue

            event = _parse(payload)
            if event is None:
                continue

            yield event
            sent += 1
            if max_events is not None and sent >= max_events:
                return


async def collect_window(
    ws_url: str,
    *,
    seconds: int,
    max_events: int = 1000,
) -> list[NewTokenEvent]:
    """Drain the stream for up to `seconds`, returning up to `max_events`."""
    out: list[NewTokenEvent] = []
    deadline = asyncio.get_event_loop().time() + seconds

    async def _consume() -> None:
        async for ev in stream_new_tokens(ws_url, max_events=max_events):
            out.append(ev)
            if asyncio.get_event_loop().time() >= deadline:
                return

    try:
        await asyncio.wait_for(_consume(), timeout=seconds + 5)
    except asyncio.TimeoutError:
        pass
    return out
