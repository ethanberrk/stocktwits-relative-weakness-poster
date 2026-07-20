from datetime import date

import pytest

import config
from src import select
from src.source.base import Candidate


def _c(ticker, watchers, mcap=2e9):
    return Candidate(ticker=ticker, name=ticker, exchange="NASDAQ", price=1.0,
                     pct_change_today=0.0, market_cap=mcap, week52_high=1.0,
                     security_type="EQUITY", watchers=watchers)


def test_validate_raises_over_gate():
    many = [_c(f"T{i}", i) for i in range(config.MAX_PLAUSIBLE_HIGHS + 1)]
    with pytest.raises(select.ValidationError):
        select.validate(many)


def test_validate_allows_at_gate():
    exactly = [_c(f"T{i}", i) for i in range(config.MAX_PLAUSIBLE_HIGHS)]
    select.validate(exactly)  # must not raise


def test_ranked_eligible_orders_by_fewest_watchers():
    cands = [_c("HIGH", 5000), _c("LOW", 3), _c("MID", 400)]
    ranked = select.ranked_eligible(cands, posted=[], today=date(2026, 7, 8))
    assert [c.ticker for c in ranked] == ["LOW", "MID", "HIGH"]


def test_ranked_eligible_is_not_truncated():
    cands = [_c(f"T{i}", i) for i in range(10)]
    ranked = select.ranked_eligible(cands, posted=[], today=date(2026, 7, 8))
    assert len(ranked) == 10  # full list, caps applied later via slot_count


def test_ranked_eligible_excludes_below_market_cap():
    cands = [_c("BIG", 1, mcap=2e9), _c("SMALL", 0, mcap=5e8)]
    ranked = select.ranked_eligible(cands, posted=[], today=date(2026, 7, 8))
    assert [c.ticker for c in ranked] == ["BIG"]  # SMALL dropped despite fewer watchers


def test_ranked_eligible_excludes_blocked():
    posted = [{"ticker": "A", "date": "2026-07-08"}]  # A already posted today
    cands = [_c("A", 1), _c("B", 2)]
    ranked = select.ranked_eligible(cands, posted, today=date(2026, 7, 8))
    assert [c.ticker for c in ranked] == ["B"]


def test_slot_count_respects_per_tick_cap(monkeypatch):
    monkeypatch.setattr(config, "MAX_PER_TICK", 2)
    monkeypatch.setattr(config, "MAX_PER_DAY", 20)
    assert select.slot_count(posted=[], today=date(2026, 7, 8)) == 2


def test_slot_count_respects_daily_remaining(monkeypatch):
    monkeypatch.setattr(config, "MAX_PER_TICK", 5)
    monkeypatch.setattr(config, "MAX_PER_DAY", 3)
    posted = [{"ticker": "X", "date": "2026-07-08"},
              {"ticker": "Y", "date": "2026-07-08"}]  # 2 posted, 1 left
    assert select.slot_count(posted, today=date(2026, 7, 8)) == 1


def test_slot_count_floors_at_zero(monkeypatch):
    monkeypatch.setattr(config, "MAX_PER_TICK", 5)
    monkeypatch.setattr(config, "MAX_PER_DAY", 2)
    posted = [{"ticker": "X", "date": "2026-07-08"},
              {"ticker": "Y", "date": "2026-07-08"},
              {"ticker": "Z", "date": "2026-07-08"}]  # over budget
    assert select.slot_count(posted, today=date(2026, 7, 8)) == 0
