"""Tests for the scoring curator."""

from __future__ import annotations

from pumpguard.curator import score_token, should_alert
from pumpguard.sources.deployer import DeployerProfile
from pumpguard.sources.pumpfun import NewTokenEvent
from pumpguard.sources.token_meta import TokenMetadata


def _make_event(
    symbol: str = "TEST",
    name: str = "Test Token",
    initial_sol: float = 1.0,
    market_cap_sol: float = 10.0,
    deployer: str = "wallet1",
) -> NewTokenEvent:
    return NewTokenEvent(
        mint="mint_" + symbol.lower(),
        symbol=symbol,
        name=name,
        deployer=deployer,
        pool="pump",
        initial_sol=initial_sol,
        market_cap_sol=market_cap_sol,
    )


def _make_meta(
    description: str = "",
    top_holder_share: float = 0.0,
    deployer_share: float = 0.0,
    twitter: str = "",
    website: str = "",
) -> TokenMetadata:
    return TokenMetadata(
        mint="test",
        holder_count=10,
        top_holder_share=top_holder_share,
        deployer_share=deployer_share,
        description=description,
        twitter=twitter,
        website=website,
    )


def test_clean_token_scores_positive() -> None:
    """A clean token with good name and liquidity should score positively."""
    event = _make_event(symbol="MOTH", name="The Last Moth")
    meta = _make_meta(description="A thoughtful token about ephemeral beauty")
    deployer = DeployerProfile(wallet="wallet1", prior_launches=0)
    scored = score_token(event, meta, deployer)
    assert scored.score > 0
    assert should_alert(scored, 0.5)


def test_shouty_name_penalty() -> None:
    """All-caps long names should be penalized."""
    event = _make_event(symbol="WIFCAT24", name="WIFCAT24SUPERMOON")
    meta = _make_meta()
    deployer = DeployerProfile(wallet="wallet2", prior_launches=0)
    scored = score_token(event, meta, deployer)
    assert any("shouty" in n for n in scored.notes)


def test_serial_offender_penalty() -> None:
    """Serial ruggers should get a heavy penalty."""
    event = _make_event()
    meta = _make_meta()
    deployer = DeployerProfile(
        wallet="badactor", prior_launches=5, prior_rugs=4
    )
    scored = score_token(event, meta, deployer)
    assert scored.score < 0
    assert any("serial" in n for n in scored.notes)


def test_concentrated_supply_penalty() -> None:
    """High top-holder share should be penalized."""
    event = _make_event()
    meta = _make_meta(top_holder_share=0.6)
    deployer = DeployerProfile(wallet="wallet3", prior_launches=0)
    scored = score_token(event, meta, deployer)
    assert any("concentrated" in n for n in scored.notes)


def test_alert_threshold() -> None:
    """should_alert should respect min_score."""
    event = _make_event()
    meta = _make_meta()
    deployer = DeployerProfile(wallet="wallet4", prior_launches=0)
    scored = score_token(event, meta, deployer)
    assert should_alert(scored, -999)  # always alert
    assert not should_alert(scored, 999)  # never alert


def test_alert_levels() -> None:
    """Alert levels should map correctly from scores."""
    event = _make_event()
    meta = _make_meta()
    deployer = DeployerProfile(wallet="wallet5", prior_launches=0)

    # Force a high score by giving it everything
    event2 = _make_event(symbol="MOTH", name="The Last Moth in November")
    meta2 = _make_meta(
        description="A" * 50, twitter="x.com/test", website="example.com"
    )
    deployer2 = DeployerProfile(wallet="wallet6", prior_launches=0)
    scored = score_token(event2, meta2, deployer2)
    assert scored.alert_level == "GREEN" or scored.alert_level == "YELLOW"
