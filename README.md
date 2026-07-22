# stocktwits-relative-weakness-poster

Posts the **most-watched** US common stocks >$1B **with ≥5,000 Stocktwits
watchers** that printed a new 52-week **low** today to a **dedicated, new
Stocktwits account**, each with a 1-year chart, framed as *crowded breakdowns*
— the watcher floor is the point: a name below it has a normal amount of
friends, not too many. Every 30 minutes the most-watched
eligible names (max 2/tick, 20/day, never on consecutive trading days) get a
`$TICKER crowded breakdown — {N} watchers along for the slide` post.

**Phase 1 — preview (current):** the cron runs dry-run. Each tick renders the
1-year chart in-process and writes what *would* be posted to
`output/YYYY-MM-DD/` (chart PNG + post text) and commits it — review a few
days of samples before going live. Needs no secrets at all.
**Phase 2 — live:** flip the workflow's run line to `python run.py --sync-state
--live` and set `STOCKTWITS_ACCESS_TOKEN` (the NEW dedicated relative-weakness
account — never the RS or 52wk-poster accounts), plus `MAX_PER_TICK=1` /
`MAX_PER_DAY=12` ramp env vars.

Inverts the **RS poster**'s data pipeline (WSJ new-52wk feed → quote
enrichment → Stocktwits watchers → rank by watchers) onto the lows side,
combined with the **52wk-poster** chart+publish engine (chart PNG → Stocktwits
API, write-ahead intent, at-most-once safety).

## Pipeline (one tick)

WSJ new-52wk-**lows** feed → Yahoo v7 bulk quotes, falling back to
stockanalysis.com when Yahoo 429s → Stocktwits watchers
(`src/source/rw_source.py`) → filter >$1B and ≥`MIN_WATCHERS` (5,000) + rank
**DESCENDING** by watchers,
most-watched first (`src/select.py`) → self-rendered 1-yr candlestick PNG from
stockanalysis.com history (`src/chart.py`, matplotlib, TradingView-light
styling; a name whose history reaches back less than `MIN_HISTORY_DAYS` ≈ 11
months is skipped as a recent IPO — its "1Y" chart would mislead — and the
next most-watched name takes the slot) → publisher (`src/publish/`) →
`state/posted.json`.

## Run locally

    pip install -r requirements-dev.txt
    python -m pytest              # unit tests
    python run.py --force         # one dry-run tick, any time — no keys needed

## Ops

- Cron: `.github/workflows/tick.yml`, dispatched every 30 min during market
  hours by an external scheduler (see below).
- Trigger: GitHub's own scheduled cron is unreliable, so this workflow is
  `workflow_dispatch`-only and a cron-job.org job fires it as the driver —
  setup in [docs/cron-job-backup.md](docs/cron-job-backup.md);
  `scripts/trigger-tick.sh` is the same call for manual/any-scheduler use.
  Safe against double-ticks (the workflow's `concurrency` group serializes
  overlapping runs).
- Secrets (this repo → Settings → Secrets → Actions):
  - `STOCKTWITS_ACCESS_TOKEN` — **the dedicated relative-weakness account's
    token** (NOT the RS or 52wk-poster accounts). Required only for Phase 2
    (live); the preview phase needs no secrets.
- Dry-run by default; `--live` requires `STOCKTWITS_ACCESS_TOKEN`.
- Spec + plan: `docs/superpowers/`.

## Durability

The WSJ feed, Yahoo crumb handshake, and stockanalysis.com endpoints are all
unofficial — they work today but can rate-limit or change shape. Yahoo already
429s datacenter IPs (it zeroed out every candidate on 2026-07-09), hence the
stockanalysis.com fallback. Two gates keep a broken feed from posting garbage:
an implausible-lows validation gate (`MAX_PLAUSIBLE_LOWS = 2000`, looser than
the RS poster's 500-highs gate, since new lows legitimately run to four digits
on broad selloff days — those are the best content days; caps control volume,
not this gate), and a tripwire that fails the tick red when a non-empty WSJ
list yields zero quotes from every source.
