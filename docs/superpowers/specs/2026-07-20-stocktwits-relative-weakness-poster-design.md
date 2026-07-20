# Stocktwits Relative-Weakness Poster — Design

**Date:** 2026-07-20
**Status:** Approved (pending spec review)

## Goal

Every 30 minutes during market hours, post the **most-watched** US common
stocks over $1B market cap that printed a **new 52-week low today** to a
**new dedicated Stocktwits account**, each with a 1-year chart, framed as
*crowded breakdowns*. The ranking axis is Stocktwits watcher count
**descending** — the more watchers, the more over-discovered the breakdown.

This is the deliberate inverse of the live
`stocktwits-relative-strength-poster` (least-watched names at new 52-week
highs, "undiscovered breakouts"). Where that account surfaces price strength
nobody is watching, this one surfaces price weakness everybody is watching.

## Relationship to the RS poster (separate repo, cloned)

This is a **separate repo** (`ethanberrk/stocktwits-relative-weakness-poster`,
local `/Users/ethanberk/stocktwits-relative-weakness-poster`) whose code is
cloned from the RS poster and then inverted. Nothing is shared: its own GitHub
Secrets, its own `state/posted.json`, its own Stocktwits account and token,
its own cron. Rationale (decided 2026-07-20): the RS poster is live and
posting daily — structural isolation means nothing built here can break it.
Accepted cost: when an unofficial upstream (WSJ feed, Yahoo crumb,
stockanalysis.com) breaks, the fix must be applied in both repos.

## What flips vs. the RS poster — exactly four things

1. **Source universe — WSJ lows instead of highs.** The identical WSJ Market
   Data Center endpoint (`type=mdc_fiftytwoweek`) already carries both lists;
   the source reads the per-exchange `lows` arrays instead of `highs`.
   Verified live 2026-07-20: `data.nasdaq.lows` (196 rows) and
   `data.nyse.lows` (43 rows) share the highs' row shape, with
   `lowToday`/`lowFiftyTwoWeek` populated (and the high fields null).
   Quote enrichment carries `fiftyTwoWeekLow` instead of `fiftyTwoWeekHigh`.
2. **Ranking — watchers descending.** `select.pick()` orders candidates
   most-watched first (RS is ascending).
3. **Copy — the "crowded breakdown" voice.** Working template:
   `$TICKER crowded breakdown — {N} watchers along for the slide`.
   Pointed, personality-forward (decided over neutral/observational and
   question framings). Constraint: the line must never claim watcher counts
   are *falling* — we only observe today's count, not its history. Exact
   wording is polished during the Phase 1 preview against real samples.
4. **Chart accent — red on the way down.** Amended during planning: the
   RS renderer is already direction-neutral (candle colors and the
   last-price pill follow the data, `src/chart.py`), so a 52-week-low
   chart renders red-accented with no code change. The flip is delivered
   as a pinned test asserting a downtrend renders with a red closing
   candle, so future styling work can't silently break the framing.

## What stays identical

- $1B market-cap floor; common-stock-only name regex (`NAME_EXCLUDE_RE`).
- Recent-IPO skip via `MIN_HISTORY_DAYS = 330` (a "1Y" chart of a 6-week-old
  listing misleads on the way down exactly as it does on the way up).
- Caps: 2 posts/tick, 20/day, never the same ticker on consecutive trading
  days; market-hours-only ticks; `--force` for manual runs.
- Yahoo v7 bulk quotes with stockanalysis.com fallback; zero-quote tripwire
  (non-empty WSJ list yielding zero quotes from every source fails the tick
  red instead of posting nothing silently).
- Publisher engine: write-ahead `pending` intent pushed before any post,
  at-most-once safety, `state/posted.json`.
- Ops: 30-minute GitHub Actions cron + cron-job.org `workflow_dispatch`
  backstop, `concurrency` group serializing overlapping runs.
- Dry-run by default; `--live` requires `STOCKTWITS_ACCESS_TOKEN`.

## One deliberate re-tune: the plausibility gate

The RS poster treats a huge feed (>500 highs) as a broken-feed signal and
halts. New lows legitimately explode on broad selloff days in a way highs
rarely do (239 lows vs. 114 highs on an ordinary flat day, 2026-07-20;
correction days run to four digits). Gate is re-pointed at parser garbage
rather than market breadth: `MAX_PLAUSIBLE_LOWS = 2000`. Volume control is
the job of the per-tick/per-day caps, not the gate. Big red days are this
account's best content days and must not trip a false halt.

## Account isolation (critical)

Posts go to a **new dedicated Stocktwits account** — not @STRelativeStrength
(bearish posts would muddy that account's identity) and not the 52wk poster's
account. Handle is Ethan's choice, needed only at Phase 2; its token is
minted the same way as the RS account's and stored only in THIS repo's
GitHub Secrets as `STOCKTWITS_ACCESS_TOKEN`.

## Rollout — two phases (same shape as the RS poster)

- **Phase 1 — preview (no secrets).** Cron runs dry-run; each tick renders
  charts in-process and commits would-be posts (PNG + text) to
  `output/YYYY-MM-DD/`. Review several days of samples; polish copy here.
- **Phase 2 — live.** Ethan creates the account, token minted and set as the
  repo secret, workflow flipped to `--sync-state --live` with the same
  gradual daily-cap ramp the RS account used (start ~12/day before 20/day).

## Testing

Port the RS poster's suite and invert the fixtures: WSJ payload fixtures keyed
on `lows`, descending-rank assertions in `select` tests, gate tests at the
new 2000 threshold, copy-template test for the new post text, chart tests
unchanged except accent assertions. The suite must pass before Phase 1's cron
is enabled.
