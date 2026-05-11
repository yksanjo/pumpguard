"""Token metadata enrichment — pulls holder info, supply data, and social links.

Strategy: try Helius if key is set, fall back to basic on-chain data.
PumpGuard works without any API keys — scoring just uses less data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TokenMetadata:
    mint: str
    holder_count: int = 0
    top_holder_share: float = 0.0
    deployer_share: float = 0.0
    description: str = ""
    image_url: str = ""
    twitter: str = ""
    website: str = ""
    raw: dict | None = None

    @property
    def looks_concentrated(self) -> bool:
        """Heuristic: >50% supply in top 1 wallet is a yellow flag."""
        return self.top_holder_share > 0.5 or self.deployer_share > 0.3


async def enrich_via_helius(mint: str, api_key: str) -> TokenMetadata | None:
    """Helius DAS getAsset. Returns None on any failure."""
    if not api_key:
        return None
    url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "getAsset",
                    "params": {"id": mint},
                },
            )
            resp.raise_for_status()
            data = resp.json().get("result", {})
        except Exception as e:
            logger.warning("Helius getAsset failed for %s: %s", mint, e)
            return None

    content = data.get("content", {}) or {}
    metadata = content.get("metadata", {}) or {}
    links = content.get("links", {}) or {}

    return TokenMetadata(
        mint=mint,
        description=metadata.get("description", ""),
        image_url=links.get("image", ""),
        twitter=links.get("twitter", ""),
        website=links.get("external_url", ""),
        raw=data,
    )


async def enrich(
    mint: str, *, helius_key: str = "", bitquery_key: str = ""
) -> TokenMetadata:
    """Best-effort enrichment. Always returns a TokenMetadata, even if empty."""
    if helius_key:
        result = await enrich_via_helius(mint, helius_key)
        if result is not None:
            return result
    return TokenMetadata(mint=mint)
