# stocktwits-relative-strength-poster

Posts the **least-watched** US common stocks >$1B that printed a new 52-week
high today to a **dedicated Stocktwits account**, each with a 1-year chart,
framed as *undiscovered breakouts*. Every 30 minutes the fewest-watched
eligible names (max 2/tick, 20/day, never on consecutive trading days) get a
`$TICKER undiscovered breakout with {N} watchers` post.

**Phase 1 — preview (current):** the cron runs dry-run. Each tick renders the
1-year chart in-process and writes what *would* be posted to
`output/YYYY-MM-DD/` (chart PNG + post text) and commits it — review a few
days of samples before going live. Needs no secrets at all.
**Phase 2 — live:** flip the workflow's run line to `python run.py --sync-state
--live` and set `STOCKTWITS_ACCESS_TOKEN` (the dedicated RS account).

Combines two prior projects: the **relative-strength** data pipeline (WSJ new
highs → quote enrichment → Stocktwits watchers → rank ascending by watchers)
and the **52wk-poster** chart+publish engine (chart PNG → Stocktwits API,
write-ahead intent, at-most-once safety).

## Pipeline (one tick)

WSJ new-52wk-highs feed → Yahoo v7 bulk quotes, falling back to
stockanalysis.com when Yahoo 429s → Stocktwits watchers
(`src/source/rs_source.py`) → filter >$1B + rank fewest-watched (`src/select.py`)
→ self-rendered 1-yr candlestick PNG from stockanalysis.com history
(`src/chart.py`, matplotlib, TradingView-light styling; a name whose
history reaches back less than `MIN_HISTORY_DAYS` ≈ 11 months is skipped
as a recent IPO — its "1Y" chart would mislead — and the next
least-watched name takes the slot) → publisher
(`src/publish/`) → `state/posted.json`.

## Run locally

    pip install -r requirements-dev.txt
    python -m pytest              # unit tests
    python run.py --force         # one dry-run tick, any time — no keys needed

## Ops

- Cron: `.github/workflows/tick.yml`, every 30 min during market hours.
- Backup trigger: GitHub's scheduled cron is unreliable, so a cron-job.org job
  fires the workflow via `workflow_dispatch` as a backstop — setup in
  [docs/cron-job-backup.md](docs/cron-job-backup.md); `scripts/trigger-tick.sh`
  is the same call for manual/any-scheduler use. Safe against double-ticks (the
  workflow's `concurrency` group serializes overlapping runs).
- Secrets (this repo → Settings → Secrets → Actions):
  - `STOCKTWITS_ACCESS_TOKEN` — **the dedicated RS account's token** (NOT the
    52wk-poster's account). Required only for Phase 2 (live); the preview
    phase needs no secrets.
- Dry-run by default; `--live` requires `STOCKTWITS_ACCESS_TOKEN`.
- Spec + plan: `docs/superpowers/`.

## Durability

The WSJ feed, Yahoo crumb handshake, and stockanalysis.com endpoints are all
unofficial — they work today but can rate-limit or change shape. Yahoo already
429s datacenter IPs (it zeroed out every candidate on 2026-07-09), hence the
stockanalysis.com fallback. Two gates keep a broken feed from posting garbage:
the implausible-highs validation gate, and a tripwire that fails the tick red
when a non-empty WSJ list yields zero quotes from every source.
