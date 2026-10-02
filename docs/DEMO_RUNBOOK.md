# Demo runbook — Dev Day

The demo must run on real market data, not the scripted fixture. This is the one blocker.
Owner: James (needs the OKX + Alpaca keys).

## Why

The frontend demo now calls `source=auto`. That means:

- If a real historical panel exists at `data/generated/nvdax_historical_5m.csv`, the demo
  uses it.
- If not, the backend falls back to the scripted scenario.
- If the backend is down entirely, the frontend falls back to the bundled fixture.

So generating the panel file is all that's needed to turn the demo from scripted to real.
Nothing else to wire.

## One command

```bash
# keys must be in .env first (see .env.example)
scripts/build_demo_panel.sh
```

This builds a Friday-close to Monday-open window and prints the state distribution. You want
to see some CHALLENGED steps. If the window has none, pass your own range:

```bash
scripts/build_demo_panel.sh 2026-09-18T14:00:00Z 2026-09-22T20:00:00Z
```

Pick a weekend where NVDAx actually drifted from NVDA. If one window is flat, try another.

## Prerequisites

In `.env` (copy from `.env.example`):

```
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_API_PASSPHRASE=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
```

Data sources the builder pulls: token price from OKX OnchainOS, NVDA bars from Alpaca,
reference from the OKX X-Perp index.

## Verify it worked

```bash
# counts should include CHALLENGED
curl 'localhost:8000/api/replay/NVDAx?source=panel' \
  | python3 -c "import sys,json,collections;print(collections.Counter(r['evidence_state'] for r in json.load(sys.stdin)))"
```

The response header `X-Valtide-Source: historical_panel` confirms it's real data, not the
scenario.

## Capture the fallback video

Once the panel shows a clean SUPPORTED -> CHALLENGED -> blocked-borrow arc, record a 75-second
screen capture of the full run. If the venue network or the chain is flaky on the day, play
the video and narrate. Never debug live in front of the panel.

## Figures to pull from the real panel (for the pitch)

Once the panel exists, read these straight off the replay and put them on one slide:

- The divergence: date, peak % gap between NVDAx and NVDA, how many hours.
- Detection latency: minutes from the gap opening to the first CHALLENGED.
- False-alarm rate: CHALLENGED count on the calm regular-session rows (should be low).

Do not use the synthetic benchmark's 23% false-flag number anywhere public — that's a
stress case with a built-in basis, not real NVDA behaviour.
