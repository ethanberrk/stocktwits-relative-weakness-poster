"""Xignite relative-weakness source: universe parsing, the day-cumulative
52wk-LOW test, watcher enrichment, candidate hygiene, and the fetch flow."""
from datetime import date

import pytest

import config
from src import xignite
from src.source import xignite_source as xs
from src.source.base import SourceError

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
AAAP|Pacer Barings CLO Market Flex ETF|G|N|N|100|Y|N
BFRGW|Bullfrog AI Holdings, Inc. - Warrants|S|N|N|100|N|N
BRKHU|Burtech Acquisition Corp II - Units|S|N|N|100|N|N
ZTST|Test Issue Inc|Q|Y|N|100|N|N
File Creation Time: 0903202614:01|||||||
"""
OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
A|Agilent Technologies, Inc. Common Stock|N|A|N|100|N|A
BRK.B|Berkshire Hathaway Inc. New Common Stock|N|BRK B|N|100|N|BRK.B
BAC$B|Bank of America Depositary Shares Preferred Series GG|N|BACpB|N|100|N|BAC-B
AAC.U|Ares Acquisition Corporation III Units|N|AAC.U|N|100|N|AAC=
SPY|SPDR S&P 500|P|SPY|Y|100|N|SPY
BTG|B2Gold Corp Common Shares|A|BTG|N|100|N|BTG
"""


def _fetch(url):
    return NASDAQ if "nasdaqlisted" in url else OTHER


def test_canonical_ticker_shapes():
    assert xs.canonical_ticker("AAPL") == "AAPL"
    assert xs.canonical_ticker("BRK.B") == "BRK-B"
    assert xs.canonical_ticker("BAC$B") is None
    assert xs.canonical_ticker("AAC.U") is None
    assert xs.canonical_ticker("BFRGW") is None
    assert xs.canonical_ticker("") is None


def test_listed_universe_filters_and_dash_form(monkeypatch):
    monkeypatch.setattr(config, "MIN_UNIVERSE_SIZE", 1)
    assert [t for t, _ in xs.listed_universe(_fetch)] == ["AAPL", "A", "BRK-B", "BTG"]


def test_listed_universe_floor_trips_on_tiny_list():
    with pytest.raises(SourceError, match="look broken"):
        xs.listed_universe(_fetch)


TODAY = date(2026, 9, 3)


def _q(**kw):
    base = {"Identifier": "NKE", "Outcome": "Success", "Date": "9/3/2026",
            "Open": 39, "High": 39.5, "Low": 37.95, "Last": 38.2,
            "Low52Weeks": 37.95, "PercentChangeFromPreviousClose": -2.1,
            "Security": {"Name": "Nike Inc", "Market": "NYSE"}}
    base.update(kw)
    return base


def test_is_new_low_day_cumulative_and_fresh():
    assert xs.is_new_low(_q(), TODAY)
    assert xs.is_new_low(_q(Low=37.95, Low52Weeks=37.9499999), TODAY)   # float slack
    assert not xs.is_new_low(_q(Low=38.5), TODAY)                       # above the low
    assert not xs.is_new_low(_q(Date="9/2/2026"), TODAY)                # stale / holiday
    assert not xs.is_new_low(_q(Low=0, Low52Weeks=0), TODAY)            # no data


def test_build_candidate_maps_fields():
    c = xs.build_candidate("NKE", "Nike (listing name)", _q(), 5.6e10, 120_000)
    assert (c.ticker, c.exchange, c.price, c.market_cap, c.week52_low, c.watchers) == \
        ("NKE", "NYSE", 38.2, 5.6e10, 37.95, 120_000)
    assert c.pct_change_today == -2.1 and c.security_type == "EQUITY"
    assert c.name == "Nike Inc"


def test_build_candidate_hygiene():
    assert xs.build_candidate("X", "n", _q(Security={"Name": "X", "Market": "OTC"}), 5e9, 10) is None
    assert xs.build_candidate("X", "n", _q(Security={"Name": "X Warrants", "Market": "NYSE"}), 5e9, 10) is None
    assert xs.build_candidate("X", "n", _q(), None, 10) is None
    assert xs.build_candidate("X", "n", _q(), config.MIN_MARKET_CAP - 1, 10) is None
    assert xs.build_candidate("X", "n", _q(), 5e9, None) is None          # no ranking axis
    assert xs.build_candidate("X", "n", _q(Last=0), 5e9, 10) is None
    # MIN_WATCHERS is select's job, not the source's
    assert xs.build_candidate("X", "n", _q(), 5e9, 1).watchers == 1


def test_fetch_candidates_prices_and_watches_only_hits(monkeypatch):
    universe = [("NKE", "Nike"), ("AAPL", "Apple"), ("SMALL", "Small Co")]
    quotes = {"NKE": _q(), "AAPL": _q(Identifier="AAPL", Low=300, Low52Weeks=225),
              "SMALL": _q(Identifier="SMALL")}
    asked_caps, asked_watch = [], []

    def caps(tks):
        asked_caps.extend(tks)
        return {"NKE": 5.6e10, "SMALL": 5e8}

    def watch(tks):
        asked_watch.extend(tks)
        return {"NKE": 120_000}
    monkeypatch.setattr(xignite, "quotes", lambda tks: quotes)
    monkeypatch.setattr(xignite, "market_caps", caps)
    monkeypatch.setattr(xs, "datetime", _FakeDT)
    out = xs.XigniteSource(universe=lambda: universe, watchers_fn=watch).fetch_candidates()
    assert asked_caps == ["NKE", "SMALL"]      # AAPL not at a low -> never priced
    assert asked_watch == ["NKE"]              # SMALL under $1B -> never watched
    assert [(c.ticker, c.watchers) for c in out] == [("NKE", 120_000)]


def test_fetch_candidates_zero_quotes_is_broken_feed(monkeypatch):
    monkeypatch.setattr(xignite, "quotes", lambda tks: {})
    with pytest.raises(SourceError, match="zero quotes"):
        xs.XigniteSource(universe=lambda: [("AAPL", "Apple")]).fetch_candidates()


def test_watchers_uses_dot_cashtag(monkeypatch):
    urls = []

    def fake_get(url, **kw):
        urls.append(url)
        return {"symbol": {"watchlist_count": 7}}
    monkeypatch.setattr(xs, "get_json", fake_get)
    assert xs.watchers(["BRK-B"]) == {"BRK-B": 7}
    assert urls[0].endswith("/BRK.B.json")


class _FakeDT:
    @staticmethod
    def now(tz=None):
        from datetime import datetime
        return datetime(2026, 9, 3, 14, 0, tzinfo=tz)
