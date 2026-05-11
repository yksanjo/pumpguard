"""PumpGuard CLI — the entry point for all commands.

Usage:
    pumpguard watch          Live stream with real-time scoring and alerts
    pumpguard scan           Collect tokens for a window, then print ranked report
    pumpguard check <mint>   One-shot analysis of any token
    pumpguard doctor         Check environment and dependencies
"""

from __future__ import annotations

import asyncio
import logging
import sys

import click

from .config import get_config
from .memory import Memory
from .curator import score_token, should_alert
from .alerts import print_alert, send_telegram_alert
from .sources.deployer import profile_from_memory
from .sources.pumpfun import collect_window, stream_new_tokens
from .sources.token_meta import enrich

logger = logging.getLogger("pumpguard")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
def cli() -> None:
    """🛡️  PumpGuard — watch pump.fun launches and get alerted before you ape."""


@cli.command()
@click.option(
    "--window",
    default=0,
    type=int,
    help="How long to watch (seconds). 0 = watch forever.",
)
@click.option(
    "--min-score",
    default=None,
    type=float,
    help="Minimum score to trigger alert (default: from env or 0.5).",
)
@click.option("--dry-run", is_flag=True, default=None, help="Print alerts only.")
def watch(
    window: int, min_score: float | None, dry_run: bool | None
) -> None:
    """Watch pump.fun in real-time, score launches, and alert on interesting finds."""
    cfg = get_config()
    _configure_logging(cfg.log_level)

    if dry_run is not None:
        cfg.dry_run = dry_run

    min_score = min_score if min_score is not None else cfg.min_alert_score
    memory = Memory(cfg.database_path)

    async def _watch() -> None:
        click.echo(
            f"🛡️  PumpGuard watching pump.fun...\n"
            f"   min score: {min_score} | dry-run: {cfg.dry_run}\n"
            f"   Press Ctrl+C to stop.\n"
        )

        seen_in_session: set[str] = set()

        async for event in stream_new_tokens(
            cfg.pump_portal_ws_url,
            max_events=None if window == 0 else None,
        ):
            if event.mint in seen_in_session:
                continue
            seen_in_session.add(event.mint)

            # Skip if already in memory
            if memory.has_seen_token(event.mint):
                continue

            # Enrich (best-effort)
            meta = await enrich(
                event.mint,
                helius_key=cfg.helius_api_key,
                bitquery_key=cfg.bitquery_api_key,
            )

            # Get deployer profile
            deployer = profile_from_memory(memory, event.deployer)

            # Score
            scored = score_token(event, meta, deployer)

            # Record in memory
            memory.record_token(
                mint=event.mint,
                symbol=event.symbol,
                name=event.name,
                deployer=event.deployer,
                score=scored.score,
            )
            memory.touch_deployer(event.deployer)

            # Print summary line for every token
            click.echo(scored.summary_line)

            # Alert if score is high enough
            if should_alert(scored, min_score):
                memory.record_alert(
                    mint=event.mint,
                    symbol=event.symbol,
                    score=scored.score,
                    alert_level=scored.alert_level,
                    message=scored.summary_line,
                )

                if cfg.dry_run:
                    print_alert(scored)
                else:
                    print_alert(scored)
                    if cfg.telegram_bot_token and cfg.telegram_chat_id:
                        await send_telegram_alert(
                            cfg.telegram_bot_token,
                            cfg.telegram_chat_id,
                            scored,
                        )

            # If window is set, stop after collecting enough
            if window > 0 and len(seen_in_session) >= window:
                click.echo(f"\n⏱️  Window of {window} events reached. Stopping.")
                break

    try:
        asyncio.run(_watch())
    except KeyboardInterrupt:
        click.echo("\n\n👋 PumpGuard stopped.")


@cli.command()
@click.option(
    "--window", default=60, type=int, help="Collection window in seconds."
)
@click.option("--top", default=10, type=int, help="Show top N tokens.")
def scan(window: int, top: int) -> None:
    """Collect tokens for a window, then print a ranked report."""
    cfg = get_config()
    _configure_logging(cfg.log_level)
    memory = Memory(cfg.database_path)

    async def _scan() -> None:
        click.echo(
            f"🔍 Scanning pump.fun for {window} seconds...\n"
        )

        events = await collect_window(
            cfg.pump_portal_ws_url, seconds=window
        )

        click.echo(f"Collected {len(events)} tokens. Scoring...\n")

        scored_tokens = []
        for event in events:
            if memory.has_seen_token(event.mint):
                continue

            meta = await enrich(
                event.mint,
                helius_key=cfg.helius_api_key,
                bitquery_key=cfg.bitquery_api_key,
            )
            deployer = profile_from_memory(memory, event.deployer)
            scored = score_token(event, meta, deployer)

            memory.record_token(
                mint=event.mint,
                symbol=event.symbol,
                name=event.name,
                deployer=event.deployer,
                score=scored.score,
            )
            memory.touch_deployer(event.deployer)

            scored_tokens.append(scored)

        # Sort by score descending
        scored_tokens.sort(key=lambda s: s.score, reverse=True)

        click.echo(f"{'Rank':<5} {'Score':<7} {'Symbol':<12} {'Name':<30} {'MCap':<10} {'Deployer':<20}")
        click.echo("-" * 90)
        for i, s in enumerate(scored_tokens[:top], 1):
            click.echo(
                f"{i:<5} {s.score:<+7.2f} {s.event.symbol:<12} "
                f"{s.event.name[:28]:<30} {s.event.market_cap_sol:<10.1f} "
                f"{s.deployer.risk_label:<20}"
            )

        if not scored_tokens:
            click.echo("No new tokens found (all already in memory).")

    asyncio.run(_scan())


@cli.command()
@click.argument("mint")
def check(mint: str) -> None:
    """One-shot analysis of any pump.fun token by mint address."""
    cfg = get_config()
    _configure_logging(cfg.log_level)
    memory = Memory(cfg.database_path)

    async def _check() -> None:
        click.echo(f"🔍 Analyzing {mint}...\n")

        # We can't get the event data without the WebSocket stream,
        # but we can check memory and do enrichment
        meta = await enrich(
            mint, helius_key=cfg.helius_api_key, bitquery_key=cfg.bitquery_api_key
        )

        click.echo(f"Metadata:")
        click.echo(f"  Description: {meta.description or '(none)'}")
        click.echo(f"  Twitter: {meta.twitter or '(none)'}")
        click.echo(f"  Website: {meta.website or '(none)'}")
        click.echo(f"  Holder count: {meta.holder_count}")
        click.echo(f"  Top holder share: {meta.top_holder_share:.1%}")
        click.echo(f"  Looks concentrated: {meta.looks_concentrated}")
        click.echo(f"")
        click.echo(f"Solscan: https://solscan.io/token/{mint}")

    asyncio.run(_check())


@cli.command()
def doctor() -> None:
    """Check environment and dependencies."""
    click.echo("🩺 PumpGuard Doctor\n")

    # Python version
    py = sys.version_info
    click.echo(f"✓ Python {py.major}.{py.minor}.{py.micro}")

    # Check imports
    ok = True
    for mod_name in ("httpx", "websockets", "click", "rich"):
        try:
            __import__(mod_name)
            click.echo(f"✓ {mod_name}")
        except ImportError:
            click.echo(f"✗ {mod_name} — not installed")
            ok = False

    # Config
    cfg = get_config()
    click.echo(f"\nConfig:")
    click.echo(f"  Database: {cfg.database_path}")
    click.echo(f"  Dry-run: {cfg.dry_run}")
    click.echo(f"  Helius key: {'✓ set' if cfg.helius_api_key else '○ not set (optional)'}")
    click.echo(f"  Telegram: {'✓ configured' if cfg.telegram_bot_token and cfg.telegram_chat_id else '○ not set (optional)'}")

    if ok:
        click.echo("\n✓ All good. Run `pumpguard watch` to start monitoring.")
    else:
        click.echo("\n✗ Some dependencies are missing. Run: pip install -e '.[dev]'")
        sys.exit(1)


if __name__ == "__main__":
    cli()
