# Prisoner’s Arena
This project exists to answer one question:

> *Under realistic conditions (noise, exploitation, limited interaction), which forms of cooperation actually survive?*

## What's inside

- **Arena** — pick fighters (2 for a detailed 1v1, more for a free-for-all round-robin), set rounds/iterations/noise, and run. Large tournaments run as background jobs with a progress bar; everything is **precomputed server-side, then replayed** in the browser.
- **Dashboard** — trading-terminal-style stat-fest: sortable ranking board (score, win rate, cooperation, retaliation speed, forgiveness, early/mid/late performance, volatility, robustness to noise), cooperation-over-time and score-race charts, head-to-head matrix heatmap, phase breakdown. Every stat has a plain-language tooltip. Discreet CSV/JSON export for researchers.
- **Replay** — all matches replayed simultaneously with a global scrubber, or isolate one match: health-bar score meters, combo/streak counters, a fight-commentary feed, noise flips marked distinctly, instant jump-to-any-round scrubbing, per-phase breakdown, and an auto-generated narrative summary.
- **Encyclopedia** — every strategy explained in plain language with a category tag and an animated demo vs Tit For Tat.
- **Builder** — a no-code IF/THEN block editor. Rules compile to a real Python function with the same pure-function interface as the built-in strategies (safely interpreted — user input is never `exec`'d). Test instantly in a sandbox against the classics, then save.
- **Marketplace** — publish strategies under an anonymous ID (no account needed) and fork other players' creations into your own workspace.

## Quick start

```bash
pip install -r requirements.txt
uvicorn api:app --reload
# open http://127.0.0.1:8000
```

## Core ideas

- Strategies are **pure functions**: input = match history (list of `(my_move, opp_move)` booleans), output = `True` (cooperate) or `False` (defect). Hand-coded Python strategies, builder-compiled strategies, and marketplace forks are all interchangeable in the simulation core.
- Tournaments are **round-robin**; payoffs follow the classical matrix (3/3, 0/5, 5/0, 1/1).
- **Noise** is a probability of a move being flipped (a misunderstanding); flips are recorded as events and surfaced in replays, charts, and exports.
- **Precompute-then-replay**: the server computes the full dataset (per-round moves, noise events, phase splits, narratives, all metrics); the frontend only animates and slices it, which is what makes instant jump-to-round scrubbing possible.

## Project structure

```
Prisoners_dilemma/
├── api.py              # FastAPI app: simulation, jobs, export, builder, marketplace
├── cli.py              # CLI entrypoint
├── storage.py          # SQLite persistence for custom strategies (anonymous ownership)
├── builder/            # No-code rule schema validation + compiler (closed vocabulary, no exec)
├── core/               # Match mechanics, payoff matrix, noise-event tracking
├── interaction/        # Noise model
├── strategies/         # Built-in strategy implementations (s01..s41)
├── simulation/         # Tournament engine, metrics, narratives, background jobs
├── evolution/          # Population dynamics over time (legacy experiments)
├── static/             # Frontend (dashboard, replay, builder, marketplace)
├── visualization/      # DEPRECATED: legacy racing-bar-chart / evolution plots
└── axelrod_lib/        # Axelrod library interop
```

## API highlights

| Endpoint | Purpose |
|---|---|
| `POST /simulate` | Run a tournament synchronously, get the full dataset |
| `POST /simulate/async` → `GET /jobs/{id}` → `GET /results/{id}` | Background job with progress for large runs |
| `GET /results/{id}/export?format=csv&dataset=rounds\|leaderboard\|matrix` | Research export (also `format=json`) |
| `POST /builder/compile` / `POST /builder/test` | Validate + preview compiled Python / sandbox vs classics |
| `POST /anon/session` | Get an anonymous ownership token (no account) |
| `GET/POST/PUT/DELETE /custom-strategies` | Manage your saved strategies |
| `GET /marketplace`, `POST /marketplace/{id}/fork` | Browse and fork published strategies |
| `GET /strategies/meta`, `GET /strategies/demo?id=…` | Strategy encyclopedia data |

## CLI

```bash
python -m cli --list-strategies
python -m cli --strategies "s01 - Always Coop" "s03 - Tit For Tat" --rounds 200 --iterations 5 --noise 0.05
```

## Requirements

- Python 3.10+
- fastapi, uvicorn, pydantic (see `requirements.txt`)
- pandas / bar_chart_race / axelrod only for the deprecated legacy scripts in `visualization/` and `evolution/`

## Deprecated

The racing bar chart (`visualization/data_rbc.py`, `simulation/data_bcr.py`) is deprecated in favor of the dashboard's stat views (ranking board, heatmap, cooperation-over-time). The scripts remain for reference but are no longer part of the product flow.
