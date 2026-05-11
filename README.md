# 🛡️ PumpGuard

> A local agent that watches pump.fun in real-time, scores launches, checks deployer history, and alerts you before you ape.

PumpGuard is a self-hosted CLI agent for the pump.fun community. It runs on **your machine** — no servers, no third-party APIs (except the free PumpPortal WebSocket), no hosting.

```bash
pumpguard watch                    # live stream with alerts
pumpguard scan --window 120        # scan for N seconds, then report
pumpguard check <MINT_ADDRESS>     # one-shot analysis of any token
pumpguard doctor                   # check your setup
```

---

## Features

- **Real-time monitoring** — connects to PumpPortal WebSocket, streams new launches
- **Smart scoring** — same anti-shill heuristics as PumpScout (name quality, liquidity, deployer history, supply concentration)
- **Deployer reputation** — tracks deployers locally in SQLite, flags serial ruggers
- **Alert system** — terminal notifications for high-scoring finds and red flags
- **Fully local** — everything runs on your machine, data stays in SQLite
- **No hosting** — no servers, no cloud, no cron. Just `pumpguard watch` in a terminal

---

## Quick start

```bash
# Install
git clone https://github.com/yksanjo/pumpguard.git
cd pumpguard
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Check your setup
pumpguard doctor

# Watch for 2 minutes (dry-run, no alerts)
pumpguard watch --window 120 --dry-run

# Watch live (with alerts)
pumpguard watch
```

---

## Commands

### `pumpguard watch`
Stream new pump.fun tokens in real-time. Each token is scored as it arrives. High-scoring tokens trigger alerts.

```
Options:
  --window INTEGER    How long to watch (seconds). Omit = watch forever.
  --min-score FLOAT   Minimum score to trigger alert (default: 0.5)
  --dry-run           Print alerts to console instead of sending notifications
  --alert-telegram    Send alerts via Telegram bot
```

### `pumpguard scan`
Collect tokens for a fixed window, then print a ranked report.

```
Options:
  --window INTEGER    Collection window in seconds (default: 60)
  --top INTEGER       Show top N tokens (default: 10)
```

### `pumpguard check <mint>`
One-shot analysis of any pump.fun token by mint address. Shows score, deployer history, and red flags.

### `pumpguard doctor`
Check that your environment is set up correctly — Python version, dependencies, WebSocket reachability.

---

## Alert levels

| Level | Color | Score range | What it means |
|-------|-------|-------------|---------------|
| 🟢 GREEN | Green | ≥ 1.0 | Interesting find — worth a look |
| 🟡 YELLOW | Yellow | ≥ 0.5 | Decent — deployer looks clean |
| 🔴 RED | Red | < 0.0 | Red flags — rug risk, serial deployer |
| ⚫ GRAY | Gray | N/A | Already seen or filtered out |

---

## Data

PumpGuard stores everything in a local SQLite database (`~/.pumpguard/pumpguard.sqlite`):

- `tokens_seen` — every token observed, with metadata
- `deployers` — deployer wallet history (launch count, rug count)
- `alerts` — every alert triggered

This means the agent gets smarter over time — it remembers deployers across sessions.

---

## Why self-hosted?

- **No third-party risk** — your alerts don't go through a server you don't control
- **No front-running** — nobody sees what you're watching
- **No hosting costs** — runs in a terminal on your laptop or VPS
- **Full control** — modify the scoring, add your own alert channels, extend as you like

---

## License

MIT — see [LICENSE](./LICENSE).

## Built with

- [PumpPortal](https://pumpportal.fun/data-api/real-time/) — free WebSocket for pump.fun deploys
- [Rich](https://rich.readthedocs.io/) — beautiful terminal UI
- [Click](https://click.palletsprojects.com/) — CLI framework
- [httpx](https://www.python-httpx.org/) — async HTTP for enrichment
