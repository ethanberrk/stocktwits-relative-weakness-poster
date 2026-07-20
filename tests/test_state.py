from datetime import date, datetime, timezone

from src import state


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "posted.json"
    state.append_posted(p, "AAA", date(2026, 7, 8), "123", status="posted")
    posts = state.load_posted(p)
    assert posts == [{"ticker": "AAA", "date": "2026-07-08",
                      "post_id": "123", "status": "posted"}]


def test_mark_posted_promotes_pending(tmp_path):
    p = tmp_path / "posted.json"
    state.append_posted(p, "BBB", date(2026, 7, 8), None, status="pending")
    state.mark_posted(p, "BBB", date(2026, 7, 8), "999")
    e = state.load_posted(p)[0]
    assert e["status"] == "posted" and e["post_id"] == "999"


def test_is_blocked_today_and_prev_trading_day():
    posted = [{"ticker": "CCC", "date": "2026-07-07", "post_id": "1", "status": "posted"}]
    # 2026-07-08 is a Wednesday; prev trading day is Tuesday 07-07
    assert state.is_blocked("CCC", posted, date(2026, 7, 8))
    assert not state.is_blocked("DDD", posted, date(2026, 7, 8))


def test_daily_count():
    posted = [{"ticker": "A", "date": "2026-07-08"},
              {"ticker": "B", "date": "2026-07-08"},
              {"ticker": "C", "date": "2026-07-07"}]
    assert state.daily_count(posted, date(2026, 7, 8)) == 2


def test_market_hours_gate():
    # 2026-07-08 14:00 UTC = 10:00 ET Wednesday -> open
    open_utc = datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)
    assert state.is_market_hours(open_utc)
    # 2026-07-08 02:00 UTC -> closed
    closed_utc = datetime(2026, 7, 8, 2, 0, tzinfo=timezone.utc)
    assert not state.is_market_hours(closed_utc)
    # Saturday 2026-07-11 14:00 UTC -> closed
    sat = datetime(2026, 7, 11, 14, 0, tzinfo=timezone.utc)
    assert not state.is_market_hours(sat)
