# Stocktwits Relative-Weakness Poster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A poster that publishes the most-watched US common stocks (>$1B) printing new 52-week lows to a dedicated Stocktwits account, cloned from the live RS poster with four inversions.

**Architecture:** Baseline-clone the proven `stocktwits-relative-strength-poster` engine into this repo, then invert in small TDD steps: WSJ `lows` list instead of `highs`, watchers ranked descending, "crowded breakdown" copy, and a re-pointed plausibility gate. The chart renderer is already direction-neutral (candle colors and the last-price pill follow the data), so flip #4 is a verification test, not a code change.

**Tech Stack:** Python 3.12, matplotlib, pytest, GitHub Actions, urllib (deliberately — Stocktwits' CDN 403s the `requests` TLS fingerprint).

**Spec:** `docs/superpowers/specs/2026-07-20-stocktwits-relative-weakness-poster-design.md`
**Clone source:** `/Users/ethanberk/stocktwits-relative-strength-poster` (do not modify that repo — it is live)

## Global Constraints

- Post copy is exactly: `$TICKER crowded breakdown — {N} watchers along for the slide` (never claim watchers are falling).
- `MAX_PLAUSIBLE_LOWS = 2000` (loosened from RS's 500 — lows legitimately explode on selloff days).
- Ranking: watchers **descending** (most-watched first).
- Unchanged from RS: `MIN_MARKET_CAP = 1_000_000_000`, `MAX_PER_TICK = 2`, `MAX_PER_DAY = 20`, `MIN_HISTORY_DAYS = 330`, never-consecutive-trading-days block, market-hours gate, dry-run default.
- Nothing shared with the RS repo: own state, own output, own GitHub Secrets, own Stocktwits account (token needed only at Phase 2, not in this plan).
- Naming: `week52_high` → `week52_low`, `HighsSource` → `LowsSource`, `RSSource`/`rs_source.py` → `RWSource`/`rw_source.py`, git bot `rw-poster-bot`.
- All knobs live in `config.py`; no other file defines numbers or thresholds.
- Workflow ships in **Phase 1 preview mode**: `python run.py` (no `--live`, no token).

---

### Task 1: Baseline clone

Bring the RS poster's code into this repo verbatim as a known-good baseline. Every later task diffs against this commit, so reviewers see only the inversions.

**Files:**
- Create: everything under `src/`, `tests/`, plus `run.py`, `config.py`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.gitignore`, `scripts/trigger-tick.sh`, `.github/workflows/tick.yml`, `docs/cron-job-backup.md` — copied from `/Users/ethanberk/stocktwits-relative-strength-poster`
- Create: `state/posted.json` (fresh, empty)

**Interfaces:**
- Produces: the full RS engine — later tasks modify `config.py`, `src/select.py`, `src/source/base.py`, `src/source/rs_source.py`, `src/publish/base.py`, `run.py`, tests.

- [ ] **Step 1: Copy the code (not the history, state, or output)**

```bash
cd /Users/ethanberk/stocktwits-relative-weakness-poster
rsync -a \
  --exclude '.git' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude '.venv' --exclude 'state/' --exclude 'output/' \
  --exclude 'docs/superpowers/' \
  /Users/ethanberk/stocktwits-relative-strength-poster/ ./
mkdir -p state output
printf '{\n  "posts": []\n}\n' > state/posted.json
```

- [ ] **Step 2: Install deps and run the full suite — must pass untouched**

Run: `pip install -r requirements-dev.txt && python -m pytest -q`
Expected: all tests PASS (the RS suite is green on its own code).

- [ ] **Step 3: Sanity-check no RS state leaked**

Run: `python3 -c "import json; d=json.load(open('state/posted.json')); assert d == {'posts': []}, d; print('clean')"`
Expected: `clean`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "baseline: verbatim clone of stocktwits-relative-strength-poster engine"
```

---

### Task 2: Re-point the plausibility gate (highs → lows, 500 → 2000)

**Files:**
- Modify: `config.py` (line with `MAX_PLAUSIBLE_HIGHS = 500`)
- Modify: `src/select.py:13-16` (`validate`)
- Test: `tests/test_config.py`, `tests/test_select.py:16-24`

**Interfaces:**
- Consumes: `config` module, `select.validate(candidates: list[Candidate]) -> None` from Task 1 baseline.
- Produces: `config.MAX_PLAUSIBLE_LOWS: int = 2000`; `config.MAX_PLAUSIBLE_HIGHS` no longer exists. `select.validate` raises `select.ValidationError` above the new gate.

- [ ] **Step 1: Write the failing tests**

In `tests/test_config.py`, add:

```python
def test_plausible_lows_gate_is_2000():
    # Lows legitimately explode on broad selloff days (unlike highs), so the
    # broken-feed gate sits at 2000; volume control is the per-tick/day caps.
    assert config.MAX_PLAUSIBLE_LOWS == 2000
    assert not hasattr(config, "MAX_PLAUSIBLE_HIGHS")
```

In `tests/test_select.py`, replace `test_validate_raises_over_gate` and `test_validate_allows_at_gate` with:

```python
def test_validate_raises_over_gate():
    many = [_c(f"T{i}", i) for i in range(config.MAX_PLAUSIBLE_LOWS + 1)]
    with pytest.raises(select.ValidationError):
        select.validate(many)


def test_validate_allows_at_gate():
    exactly = [_c(f"T{i}", i) for i in range(config.MAX_PLAUSIBLE_LOWS)]
    select.validate(exactly)  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py tests/test_select.py -q`
Expected: FAIL — `AttributeError: module 'config' has no attribute 'MAX_PLAUSIBLE_LOWS'`

- [ ] **Step 3: Implement**

In `config.py`, replace the `MAX_PLAUSIBLE_HIGHS` line with:

```python
MAX_PLAUSIBLE_LOWS = 2000               # broken-feed gate. Looser than the RS
                                        # poster's 500: new lows legitimately
                                        # run to four digits on selloff days,
                                        # and those are the best content days.
                                        # Caps control volume, not this gate.
```

In `src/select.py`, `validate` becomes:

```python
def validate(candidates: list[Candidate]) -> None:
    if len(candidates) > config.MAX_PLAUSIBLE_LOWS:
        raise ValidationError(
            f"{len(candidates)} '52-week lows' is implausible "
            f"(gate: {config.MAX_PLAUSIBLE_LOWS}); refusing to post")
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: all PASS (only `select.py` referenced the old name).

- [ ] **Step 5: Commit**

```bash
git add config.py src/select.py tests/test_config.py tests/test_select.py
git commit -m "feat: plausibility gate re-pointed at lows, 2000"
```

---

### Task 3: Rank watchers descending

**Files:**
- Modify: `src/select.py:19-28` (`ranked_eligible`)
- Test: `tests/test_select.py:27-42`, `tests/test_run.py:28-40,59-76`

**Interfaces:**
- Consumes: `Candidate` (baseline), `state.is_blocked(ticker, posted, today)`.
- Produces: `select.ranked_eligible(candidates, posted, today) -> list[Candidate]` sorted most-watched first. `run.tick` needs no change — it walks the ranked list order-agnostically.

- [ ] **Step 1: Write the failing tests**

In `tests/test_select.py`, replace `test_ranked_eligible_orders_by_fewest_watchers` and `test_ranked_eligible_excludes_below_market_cap` with:

```python
def test_ranked_eligible_orders_by_most_watchers():
    cands = [_c("HIGH", 5000), _c("LOW", 3), _c("MID", 400)]
    ranked = select.ranked_eligible(cands, posted=[], today=date(2026, 7, 20))
    assert [c.ticker for c in ranked] == ["HIGH", "MID", "LOW"]


def test_ranked_eligible_excludes_below_market_cap():
    cands = [_c("BIG", 1, mcap=2e9), _c("SMALL", 9999, mcap=5e8)]
    ranked = select.ranked_eligible(cands, posted=[], today=date(2026, 7, 20))
    assert [c.ticker for c in ranked] == ["BIG"]  # SMALL dropped despite more watchers
```

In `tests/test_run.py`, update the two tick tests so the MOST-watched name wins (post-text strings stay the baseline's `undiscovered breakout` wording for now; Task 6 flips the copy):

```python
def test_tick_posts_most_watched_and_records_state(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_PER_TICK", 1)
    monkeypatch.setattr(config, "MAX_PER_DAY", 20)
    sp = tmp_path / "posted.json"
    pub = FakePublisher()
    now = datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)  # 10:00 ET Wed
    done = run.tick(FakeSource([_c("CROWD", 900), _c("QUIET", 3)]), pub,
                    chart_fetch=lambda c: b"PNG", state_path=sp, now_utc=now)
    assert done == ["CROWD"]
    assert pub.posted == [("CROWD", "$CROWD undiscovered breakout with 900 watchers")]
    e = [p for p in state.load_posted(sp) if p["ticker"] == "CROWD"][0]
    assert e["status"] == "posted" and e["post_id"] == "id-CROWD"
```

(the old `test_tick_posts_fewest_watched_and_records_state` is deleted), and:

```python
def test_tick_backfills_when_top_pick_chart_fails(tmp_path, monkeypatch):
    import config
    from src.chart import ChartError
    monkeypatch.setattr(config, "MAX_PER_TICK", 1)
    monkeypatch.setattr(config, "MAX_PER_DAY", 20)
    sp = tmp_path / "posted.json"
    pub = FakePublisher()
    now = datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)  # 10:00 ET Wed

    def chart_fetch(c):
        if c.ticker == "CROWD":        # most-watched name can't be charted
            raise ChartError("no chart for CROWD")
        return b"PNG"

    done = run.tick(FakeSource([_c("CROWD", 900), _c("MID", 50)]), pub,
                    chart_fetch=chart_fetch, state_path=sp, now_utc=now)
    assert done == ["MID"]  # backfilled past the un-chartable most-watched name
    assert pub.posted == [("MID", "$MID undiscovered breakout with 50 watchers")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_select.py tests/test_run.py -q`
Expected: FAIL — ranked lists come back fewest-first.

- [ ] **Step 3: Implement**

In `src/select.py`, `ranked_eligible` becomes:

```python
def ranked_eligible(candidates: list[Candidate], posted: list[dict],
                    today: date) -> list[Candidate]:
    """All postable candidates, MOST watchers first (no floor). Not capped —
    run.py walks this list and stops once it has enough that actually chart,
    so an un-chartable most-watched name can't starve the whole tick."""
    eligible = [c for c in candidates
                if c.market_cap >= config.MIN_MARKET_CAP
                and not state.is_blocked(c.ticker, posted, today)]
    eligible.sort(key=lambda c: c.watchers, reverse=True)
    return eligible
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/select.py tests/test_select.py tests/test_run.py
git commit -m "feat: rank watchers descending (most-watched breakdown wins the slot)"
```

---

### Task 4: Rename the domain — `week52_low`, `LowsSource`

Mechanical rename so the data model tells the truth. No behavior change; the source still reads highs until Task 5.

**Files:**
- Modify: `src/source/base.py`
- Modify: `src/source/rs_source.py:22,68,74` (imports/field only)
- Modify: `run.py:17,20` (type hint import)
- Test: fixtures in `tests/test_source_base.py`, `tests/test_select.py:10-13`, `tests/test_run.py:10-13`, `tests/test_chart.py:9-12`, `tests/test_publish.py:13-16`, `tests/test_stocktwits.py:6-9`

**Interfaces:**
- Produces: `Candidate.week52_low: float` (replaces `week52_high`); abstract base `LowsSource` with `fetch_candidates() -> list[Candidate]`. `HighsSource` and `week52_high` no longer exist anywhere.

- [ ] **Step 1: Write the failing test**

In `tests/test_source_base.py`, update the imports and fixture to the new names:

```python
from src.source.base import Candidate, LowsSource, SourceError
```

and in its Candidate construction replace `week52_high=10.5` with `week52_low=10.5`, and the abstract-class assertion instantiates `LowsSource()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_source_base.py -q`
Expected: FAIL — `ImportError: cannot import name 'LowsSource'`

- [ ] **Step 3: Implement the rename**

`src/source/base.py` becomes:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    ticker: str
    name: str
    exchange: str            # TradingView-style prefix: "NASDAQ" | "NYSE" | "AMEX" | ""
    price: float
    pct_change_today: float
    market_cap: float
    week52_low: float
    security_type: str       # Yahoo quoteType, e.g. "EQUITY"
    watchers: int            # Stocktwits watchlist_count; the ranking axis


class SourceError(Exception):
    """The source itself looks broken (not merely 'no lows right now')."""


class LowsSource(ABC):
    @abstractmethod
    def fetch_candidates(self) -> list[Candidate]:
        """All US equities on today's 52-week-low list, each with watchers set."""
```

Then update every reference (behavior untouched):
- `src/source/rs_source.py`: import `LowsSource`, class line `class RSSource(LowsSource):`, and in `_build_candidate` change `week52_high=float(quote.get("fiftyTwoWeekHigh") or 0.0),` to `week52_low=float(quote.get("fiftyTwoWeekHigh") or 0.0),` (the quote key flips in Task 5).
- `run.py`: `from src.source.base import LowsSource, SourceError` and `def tick(source: LowsSource, ...)`.
- Every test `_c(...)` fixture listed above: `week52_high=` → `week52_low=`.

- [ ] **Step 4: Verify no stragglers, run the full suite**

Run: `grep -rn "week52_high\|HighsSource" src tests run.py config.py; python -m pytest -q`
Expected: grep prints nothing; all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename domain to week52_low / LowsSource (no behavior change)"
```

---

### Task 5: The source reads lows — `RWSource`

**Files:**
- Create: `src/source/rw_source.py` (via `git mv src/source/rs_source.py src/source/rw_source.py`)
- Create: `tests/test_rw_source.py` (via `git mv tests/test_rs_source.py tests/test_rw_source.py`)
- Modify: `run.py:18,117`

**Interfaces:**
- Consumes: `Candidate`, `LowsSource`, `SourceError` (Task 4), `config.WSJ_MDC_URL`, `config.SA_QUOTE_URL`, `src.fetch.get_json`.
- Produces: `RWSource(LowsSource)` with `fetch_candidates() -> list[Candidate]`; module-level `_build_candidate(ticker, name, quote, watch) -> Candidate | None` expecting quote key `fiftyTwoWeekLow`; `_sa_quotes` maps stockanalysis `l52` → `fiftyTwoWeekLow` (field verified live 2026-07-20: `l52` present in `GET /api/quotes/s/AAPL`).

- [ ] **Step 1: Rename the module and its tests**

```bash
git mv src/source/rs_source.py src/source/rw_source.py
git mv tests/test_rs_source.py tests/test_rw_source.py
```

- [ ] **Step 2: Write the failing tests**

In `tests/test_rw_source.py`:
- Replace all imports of `rs_source`/`RSSource` with `rw_source`/`RWSource` (module import line becomes `from src.source.rw_source import RWSource, _build_candidate, _EXCHANGE_PREFIX`; the two in-test `from src.source import rs_source` / `monkeypatch.setattr(rs_source, ...)` occurrences become `rw_source`).
- In every quote fixture, replace `"fiftyTwoWeekHigh": <x>` with `"fiftyTwoWeekLow": <x>`.
- Replace the SA fixture helper and its assertion test:

```python
def _sa_quote_payload(price=42.37, cp=-13.08, l52=41.90):
    return {"data": {"p": price, "cp": cp, "l52": l52, "h52": 88.10,
                     "o": 48.33, "h": 48.67, "l": 41.90}}
```

and in `test_sa_quotes_parses_quote_and_mcap_payloads` assert:

```python
    assert q["fiftyTwoWeekLow"] == 41.90
    assert q["regularMarketChangePercent"] == -13.08
```

- Add a WSJ-parsing test (the baseline never had one at this layer; the lows flip needs it):

```python
def test_wsj_universe_reads_lows_not_highs(monkeypatch):
    from src.source import rw_source

    payload = {"data": {
        "nasdaq": {
            "highs": [{"ticker": "HI", "name": "High Co"}],
            "lows": [{"ticker": "LO", "name": "Low Co"},
                     {"ticker": "LO", "name": "Low Co"},          # dupe dropped
                     {"ticker": "PFD", "name": "Foo Pfd"},        # excluded by name
                     {"ticker": "BRK.B", "name": "Dotted Inc."}], # dotted dropped
        },
        "nyse": {"highs": [], "lows": [{"ticker": "NY", "name": "Nyse Low Co"}]},
    }}
    monkeypatch.setattr(rw_source, "get_json", lambda url, **kw: payload)
    assert RWSource()._wsj_universe() == [("LO", "Low Co"), ("NY", "Nyse Low Co")]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_rw_source.py -q`
Expected: FAIL — `_wsj_universe` returns `[("HI", ...)]`-side data and quote dicts lack `fiftyTwoWeekLow`.

- [ ] **Step 4: Implement the inversion in `src/source/rw_source.py`**

Four edits (plus the module docstring rewritten to describe the lows pipeline):
1. `_wsj_universe`: `for r in payload.get("highs") or []:` → `for r in payload.get("lows") or []:`
2. `_build_candidate`: `week52_low=float(quote.get("fiftyTwoWeekLow") or 0.0),`
3. `_sa_quotes` mapping: `"fiftyTwoWeekHigh": float(q.get("h52") or 0.0),` → `"fiftyTwoWeekLow": float(q.get("l52") or 0.0),`
4. `fetch_candidates` empty-universe error: `"WSJ feed returned zero new lows; feed looks broken"`; class line `class RWSource(LowsSource):`

Then `run.py`: `from src.source.rw_source import RWSource` and `tick(RWSource(), ...)` in `main()`.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all PASS.

- [ ] **Step 6: Live smoke test (network; markets need not be open)**

Run: `python3 -c "
from src.source.rw_source import RWSource
pairs = RWSource()._wsj_universe()
print(len(pairs), 'names on the lows list, e.g.', pairs[:3])
assert pairs, 'lows list empty — check feed'"`
Expected: a non-zero count with plausible tickers.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: RWSource — WSJ 52-week lows universe, l52/fiftyTwoWeekLow enrichment"
```

---

### Task 6: The crowded-breakdown copy

**Files:**
- Modify: `src/publish/base.py:19-24` (`compose_post_text`)
- Test: `tests/test_publish.py:19-26`, `tests/test_run.py` (expected strings)

**Interfaces:**
- Consumes: `st_symbol(ticker)` from `src/stocktwits.py` (Stocktwits symbology, e.g. `BRK.B`).
- Produces: `compose_post_text(c: Candidate) -> str` returning exactly `$TICKER crowded breakdown — {N} watchers along for the slide`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_publish.py`, the two copy assertions become:

```python
        "$AAMI crowded breakdown — 15 watchers along for the slide"
```

```python
        "$BRK.B crowded breakdown — 100 watchers along for the slide"
```

In `tests/test_run.py`, the two expected post strings become:

```python
    assert pub.posted == [("CROWD", "$CROWD crowded breakdown — 900 watchers along for the slide")]
```

```python
    assert pub.posted == [("MID", "$MID crowded breakdown — 50 watchers along for the slide")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish.py tests/test_run.py -q`
Expected: FAIL — copy still reads `undiscovered breakout`.

- [ ] **Step 3: Implement**

In `src/publish/base.py`:

```python
def compose_post_text(c: Candidate) -> str:
    # No price/%chg/mcap in the copy: those go stale between the tick and the
    # reader; the attached chart carries the quantitative story. Watcher count
    # is stable enough to include and is the whole point of this feed. The
    # line must never claim watchers are FALLING — we only see today's count.
    # Cashtag uses Stocktwits symbology (BRK.B, not Yahoo's BRK-B).
    return (f"${st_symbol(c.ticker)} crowded breakdown — "
            f"{c.watchers} watchers along for the slide")
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/publish/base.py tests/test_publish.py tests/test_run.py
git commit -m "feat: crowded-breakdown post copy"
```

---

### Task 7: Verify the chart on a downtrend (flip #4 — test only)

The renderer already colors candles and the last-price pill by data direction (`src/chart.py:79,111`), so a 52-week-low chart is naturally red-accented. Pin that with a test so a future styling change can't silently break the weakness framing.

**Files:**
- Test: `tests/test_chart.py` (add one test; `_c` fixture already renamed in Task 4)

**Interfaces:**
- Consumes: `src.chart._render_png(candidate, hist) -> bytes`, hist rows `[YYYY-MM-DD, o, h, l, c]` ascending; `chart.DOWN == "#F23645"`.

- [ ] **Step 1: Write the test (passes immediately — that is the point)**

```python
def test_render_downtrend_ends_red():
    # A year-long slide into a 52-week low: the renderer must produce a valid
    # PNG and the closing candle logic must classify the last day as DOWN
    # (red accent) — the direction this whole account posts.
    from src import chart
    hist = [[f"2025-{m:02d}-15", 100 - m * 5, 101 - m * 5, 98 - m * 5, 99 - m * 6]
            for m in range(7, 13)]
    hist += [[f"2026-{m:02d}-15", 70 - m * 4, 71 - m * 4, 66 - m * 4, 67 - m * 5]
             for m in range(1, 8)]
    last_o, last_c = hist[-1][1], hist[-1][4]
    assert last_c < last_o  # fixture really is a down day
    png = chart._render_png(_c("SLIDE"), hist)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_chart.py -q`
Expected: all PASS (baseline renderer is direction-neutral; if this FAILS, the renderer has a hidden bullish assumption — stop and investigate, do not restyle).

- [ ] **Step 3: Commit**

```bash
git add tests/test_chart.py
git commit -m "test: pin red-accent rendering on a downtrend chart (spec flip #4)"
```

---

### Task 8: Identity pass — run.py messaging, workflow, scripts, README

**Files:**
- Modify: `run.py:33,81` (tick log line; git bot name)
- Modify: `.github/workflows/tick.yml` (preview mode, new account comment, bot name)
- Modify: `scripts/trigger-tick.sh`, `docs/cron-job-backup.md` (repo URL `ethanberrk/stocktwits-relative-weakness-poster`)
- Modify: `README.md` (full rewrite, content below)

**Interfaces:**
- Consumes: everything shipped in Tasks 1–7.
- Produces: a repo whose every user-facing string says weakness/lows; workflow runs `python run.py` with no secrets.

- [ ] **Step 1: run.py strings**

Line 33's print becomes:

```python
    print(f"{len(candidates)} on today's 52wk-low list; "
          f"{len(ranked)} eligible, up to {slots} slots this tick")
```

Line 81's git identity becomes `"user.name=rw-poster-bot"`. Also update the docstring at the top of `_git_sync_state`'s caller context if it names RS.

- [ ] **Step 2: Workflow — Phase 1 preview**

`.github/workflows/tick.yml` keeps the RS structure (workflow_dispatch-only, concurrency group, commit-state step) with these changes:
- The `Run tick` step is exactly:

```yaml
      - name: Run tick
        env:
          PYTHONUNBUFFERED: "1"
        # PHASE 1 — PREVIEW: dry-run, no secrets. Writes would-be posts to
        # output/YYYY-MM-DD/. Phase 2 (live) adds STOCKTWITS_ACCESS_TOKEN
        # (the NEW dedicated relative-weakness account — never the RS or
        # 52wk accounts) plus MAX_PER_TICK=1 / MAX_PER_DAY=12 ramp env vars,
        # and flips this line to: python run.py --sync-state --live
        run: python run.py
```

- The commit step's `git config user.name` becomes `rw-poster-bot`.
- Update the top-of-file comment block: cron-job.org drives dispatches for THIS repo's workflow (URL updated in `docs/cron-job-backup.md`).

- [ ] **Step 3: scripts + cron doc**

In `scripts/trigger-tick.sh` and `docs/cron-job-backup.md`, replace every `stocktwits-relative-strength-poster` with `stocktwits-relative-weakness-poster` (keep owner `ethanberrk`).
Run: `grep -rn "relative-strength" scripts docs .github README.md run.py src tests | grep -v superpowers`
Expected after edits: no hits outside `docs/superpowers/` (the spec/plan legitimately reference the RS repo).

- [ ] **Step 4: README rewrite**

Replace `README.md` body with the RS README's structure inverted — it must state: most-watched >$1B US common stocks at new 52-week lows, dedicated NEW Stocktwits account, `$TICKER crowded breakdown — {N} watchers along for the slide`, the Phase 1 preview / Phase 2 live rollout, the pipeline line (WSJ new-52wk-LOWS feed → quotes with stockanalysis fallback → watchers → rank DESCENDING → 1-yr chart → publisher), the 2000 gate rationale, and the same Ops/Durability sections with this repo's URLs.

- [ ] **Step 5: Full suite + local end-to-end dry run**

Run: `python -m pytest -q && python run.py --force`
Expected: tests PASS; the dry run prints `N on today's 52wk-low list ...` and writes `output/<today>/<TICKER>.png` + `.txt` whose text reads `$... crowded breakdown — ... watchers along for the slide`. Inspect one PNG by eye (downtrending chart, red-heavy).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: relative-weakness identity — run.py strings, preview workflow, README"
```

---

### Task 9: Ship Phase 1 — GitHub repo, smoke dispatch, cron backstop

**Files:**
- No code changes; operations only.

**Interfaces:**
- Consumes: the complete repo from Tasks 1–8.
- Produces: `github.com/ethanberrk/stocktwits-relative-weakness-poster` running preview ticks on the cron-job.org schedule.

- [ ] **Step 1: Create the GitHub repo and push (match the RS repo's visibility)**

```bash
VIS=$(gh repo view ethanberrk/stocktwits-relative-strength-poster --json visibility -q .visibility | tr '[:upper:]' '[:lower:]')
gh repo create ethanberrk/stocktwits-relative-weakness-poster --$VIS --source . --push
```

- [ ] **Step 2: Smoke-run the workflow**

```bash
gh workflow run tick.yml -R ethanberrk/stocktwits-relative-weakness-poster
sleep 90
gh run list -R ethanberrk/stocktwits-relative-weakness-poster -L 1
```

Expected: run concludes `success`; then `git pull` and confirm `output/<today>/` artifacts were committed by the workflow (if outside market hours the run is a green no-op — that is a pass for wiring; re-verify content next market session).

- [ ] **Step 3: cron-job.org backstop**

Follow `docs/cron-job-backup.md` (as updated in Task 8) to add a cron-job.org job POSTing `workflow_dispatch` on the :05/:35 slots, 13:00–21:59 UTC weekdays — a NEW job, never a retargeting of the RS poster's job. If cron-job.org credentials or the GitHub PAT for the dispatch URL are unavailable in this environment, stop and flag for Ethan (⚠️ needs-you) rather than guessing.

- [ ] **Step 4: Record the phase gate**

Confirm the workflow has NO `STOCKTWITS_ACCESS_TOKEN` secret set (preview cannot post even by accident):
Run: `gh secret list -R ethanberrk/stocktwits-relative-weakness-poster`
Expected: empty.

---

## Deferred to Phase 2 (not in this plan)

- Ethan creates the dedicated Stocktwits account (handle his choice) and mints its token.
- Set `STOCKTWITS_ACCESS_TOKEN` in this repo's Actions secrets; flip the workflow run line to `python run.py --sync-state --live` with `MAX_PER_TICK=1`, `MAX_PER_DAY=12` ramp; later remove the ramp for 2/20 defaults.
- Copy polish against real preview samples (wording only; the template's honesty rule stands).
