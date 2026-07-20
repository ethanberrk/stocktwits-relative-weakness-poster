from datetime import date, datetime, timezone
from pathlib import Path

import run
from src import state
from src.publish.base import PostResult
from src.source.base import Candidate


def _c(ticker, watchers=1):
    return Candidate(ticker=ticker, name=ticker, exchange="NASDAQ", price=1.0,
                     pct_change_today=0.0, market_cap=2e9, week52_high=1.0,
                     security_type="EQUITY", watchers=watchers)


class FakeSource:
    def __init__(self, cands): self._c = cands
    def fetch_candidates(self): return self._c


class FakePublisher:
    def __init__(self): self.posted = []
    def post(self, candidate, text, image_png):
        self.posted.append((candidate.ticker, text))
        return PostResult(post_id="id-" + candidate.ticker, dry_run=False)


def test_tick_posts_fewest_watched_and_records_state(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_PER_TICK", 1)
    monkeypatch.setattr(config, "MAX_PER_DAY", 20)
    sp = tmp_path / "posted.json"
    pub = FakePublisher()
    now = datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)  # 10:00 ET Wed
    done = run.tick(FakeSource([_c("HIGH", 900), _c("LOW", 3)]), pub,
                    chart_fetch=lambda c: b"PNG", state_path=sp, now_utc=now)
    assert done == ["LOW"]
    assert pub.posted == [("LOW", "$LOW undiscovered breakout with 3 watchers")]
    e = [p for p in state.load_posted(sp) if p["ticker"] == "LOW"][0]
    assert e["status"] == "posted" and e["post_id"] == "id-LOW"


def test_tick_noop_outside_market_hours(tmp_path):
    sp = tmp_path / "posted.json"
    pub = FakePublisher()
    now = datetime(2026, 7, 8, 2, 0, tzinfo=timezone.utc)  # 22:00 ET prev day
    done = run.tick(FakeSource([_c("LOW", 3)]), pub,
                    chart_fetch=lambda c: b"PNG", state_path=sp, now_utc=now)
    assert done == [] and pub.posted == []


def test_build_publisher_live_without_token_exits(monkeypatch, tmp_path):
    import pytest
    monkeypatch.delenv("STOCKTWITS_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        run.build_publisher(live=True, out_dir=tmp_path, today=date(2026, 7, 8))


def test_tick_backfills_when_top_pick_chart_fails(tmp_path, monkeypatch):
    import config
    from src.chart import ChartError
    monkeypatch.setattr(config, "MAX_PER_TICK", 1)
    monkeypatch.setattr(config, "MAX_PER_DAY", 20)
    sp = tmp_path / "posted.json"
    pub = FakePublisher()
    now = datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)  # 10:00 ET Wed

    def chart_fetch(c):
        if c.ticker == "LOW":          # fewest-watched name can't be charted
            raise ChartError("no chart for LOW")
        return b"PNG"

    done = run.tick(FakeSource([_c("LOW", 3), _c("MID", 50)]), pub,
                    chart_fetch=chart_fetch, state_path=sp, now_utc=now)
    assert done == ["MID"]  # backfilled past the un-chartable fewest-watched name
    assert pub.posted == [("MID", "$MID undiscovered breakout with 50 watchers")]
