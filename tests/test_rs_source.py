from src.source.rs_source import RSSource, _build_candidate, _EXCHANGE_PREFIX


def test_exchange_prefix_covers_stocktwits_strings():
    assert _EXCHANGE_PREFIX["NYSE"] == "NYSE"
    assert _EXCHANGE_PREFIX["NASDAQ"] == "NASDAQ"
    assert _EXCHANGE_PREFIX["NYSEAmerican"] == "AMEX"
    assert _EXCHANGE_PREFIX["AMEX"] == "AMEX"
    assert _EXCHANGE_PREFIX["NYSEArca"] == "AMEX"
    assert _EXCHANGE_PREFIX["BATS"] == "BATS"


def test_build_candidate_happy_path():
    quote = {"marketCap": 2_000_000_000, "regularMarketPrice": 84.99,
             "regularMarketChangePercent": 3.2, "fiftyTwoWeekHigh": 85.08,
             "quoteType": "EQUITY"}
    watch = {"watchlist_count": 15, "exchange": "NYSE"}
    c = _build_candidate("AAMI", "Acadian Asset Management Inc.", quote, watch)
    assert c is not None
    assert c.ticker == "AAMI" and c.watchers == 15
    assert c.exchange == "NYSE" and c.market_cap == 2_000_000_000


def test_build_candidate_drops_below_one_billion():
    quote = {"marketCap": 500_000_000, "regularMarketPrice": 10.0,
             "fiftyTwoWeekHigh": 10.0, "quoteType": "EQUITY"}
    assert _build_candidate("SMALL", "Small Co", quote, {"watchlist_count": 1,
                            "exchange": "NYSE"}) is None


def test_build_candidate_drops_missing_watchers():
    quote = {"marketCap": 2e9, "regularMarketPrice": 10.0,
             "fiftyTwoWeekHigh": 10.0, "quoteType": "EQUITY"}
    assert _build_candidate("NOWATCH", "No Watch", quote,
                            {"watchlist_count": None, "exchange": "NYSE"}) is None


def test_build_candidate_drops_unmappable_exchange():
    quote = {"marketCap": 2e9, "regularMarketPrice": 10.0,
             "fiftyTwoWeekHigh": 10.0, "quoteType": "EQUITY"}
    assert _build_candidate("OTCX", "Otc Co", quote,
                            {"watchlist_count": 5, "exchange": "OTC"}) is None


def test_build_candidate_drops_missing_marketcap():
    quote = {"regularMarketPrice": 10.0, "fiftyTwoWeekHigh": 10.0,
             "quoteType": "EQUITY"}
    assert _build_candidate("NOMC", "No MC", quote,
                            {"watchlist_count": 5, "exchange": "NYSE"}) is None


def test_build_candidate_drops_missing_price():
    quote = {"marketCap": 2e9, "fiftyTwoWeekHigh": 10.0, "quoteType": "EQUITY"}
    assert _build_candidate("NOPRICE", "No Price", quote,
                            {"watchlist_count": 5, "exchange": "NYSE"}) is None


def test_fetch_candidates_wires_stages(monkeypatch):
    src = RSSource()
    monkeypatch.setattr(src, "_wsj_universe",
                        lambda: [("AAMI", "Acadian Asset Management Inc."),
                                 ("SMALL", "Small Co")])
    monkeypatch.setattr(src, "_yahoo_quotes", lambda tks: {
        "AAMI": {"marketCap": 3e9, "regularMarketPrice": 85.0,
                 "regularMarketChangePercent": 3.2, "fiftyTwoWeekHigh": 85.1,
                 "quoteType": "EQUITY"},
        "SMALL": {"marketCap": 5e8, "regularMarketPrice": 10.0,
                  "fiftyTwoWeekHigh": 10.0, "quoteType": "EQUITY"}})
    monkeypatch.setattr(src, "_watchers", lambda tks: {
        "AAMI": {"watchlist_count": 15, "exchange": "NYSE"},
        "SMALL": {"watchlist_count": 2, "exchange": "NYSE"}})
    cands = src.fetch_candidates()
    assert [c.ticker for c in cands] == ["AAMI"]  # SMALL dropped (<$1B)
    assert cands[0].watchers == 15


def test_fetch_candidates_raises_on_empty_universe(monkeypatch):
    import pytest
    from src.source.base import SourceError
    src = RSSource()
    monkeypatch.setattr(src, "_wsj_universe", lambda: [])
    with pytest.raises(SourceError):
        src.fetch_candidates()


# --- stockanalysis.com fallback quote stage ---

def _sa_quote_payload(price=42.37, cp=13.08, h52=42.67):
    return {"data": {"p": price, "cp": cp, "h52": h52, "o": 38.33,
                     "h": 42.67, "l": 38.33}}


def _sa_page_payload(mcap="5.38B"):
    # SvelteKit __data.json shape: objects map keys to indices into `data`.
    return {"nodes": [None, {"type": "data",
                             "data": [{"marketCap": 1}, mcap]}]}


def test_parse_abbrev_number_handles_suffixes():
    from src.source.rs_source import _parse_abbrev_number
    assert _parse_abbrev_number("5.38B") == 5.38e9
    assert _parse_abbrev_number("950M") == 950e6
    assert _parse_abbrev_number("1.2T") == 1.2e12
    assert _parse_abbrev_number(2_000_000_000) == 2e9
    assert _parse_abbrev_number("n/a") is None
    assert _parse_abbrev_number(None) is None


def test_sa_quotes_parses_quote_and_mcap_payloads(monkeypatch):
    import config
    from src.source import rs_source

    def fake_get_json(url, **kw):
        if url == config.SA_QUOTE_URL.format(ticker="AAMI"):
            return _sa_quote_payload()
        if url == config.SA_PAGE_DATA_URL.format(ticker_lower="aami"):
            return _sa_page_payload("5.38B")
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(rs_source, "get_json", fake_get_json)
    out = RSSource()._sa_quotes(["AAMI"])
    q = out["AAMI"]
    assert q["marketCap"] == 5.38e9
    assert q["regularMarketPrice"] == 42.37
    assert q["regularMarketChangePercent"] == 13.08
    assert q["fiftyTwoWeekHigh"] == 42.67


def test_sa_quotes_drops_ticker_when_mcap_missing(monkeypatch):
    import config
    from src.source import rs_source

    def fake_get_json(url, **kw):
        if "api/quotes" in url:
            return _sa_quote_payload()
        return {"nodes": []}  # no marketCap anywhere

    monkeypatch.setattr(rs_source, "get_json", fake_get_json)
    assert RSSource()._sa_quotes(["AAMI"]) == {}


def test_fetch_candidates_falls_back_to_stockanalysis_when_yahoo_empty(monkeypatch):
    src = RSSource()
    monkeypatch.setattr(src, "_wsj_universe", lambda: [("AAMI", "Acadian Inc.")])
    monkeypatch.setattr(src, "_yahoo_quotes", lambda tks: {})
    monkeypatch.setattr(src, "_sa_quotes", lambda tks: {
        "AAMI": {"marketCap": 3e9, "regularMarketPrice": 85.0,
                 "regularMarketChangePercent": 3.2, "fiftyTwoWeekHigh": 85.1,
                 "quoteType": "EQUITY"}})
    monkeypatch.setattr(src, "_watchers", lambda tks: {
        "AAMI": {"watchlist_count": 15, "exchange": "NYSE"}})
    cands = src.fetch_candidates()
    assert [c.ticker for c in cands] == ["AAMI"]
    assert cands[0].market_cap == 3e9


def test_fetch_candidates_skips_fallback_when_yahoo_works(monkeypatch):
    src = RSSource()
    monkeypatch.setattr(src, "_wsj_universe", lambda: [("AAMI", "Acadian Inc.")])
    monkeypatch.setattr(src, "_yahoo_quotes", lambda tks: {
        "AAMI": {"marketCap": 3e9, "regularMarketPrice": 85.0,
                 "regularMarketChangePercent": 3.2, "fiftyTwoWeekHigh": 85.1,
                 "quoteType": "EQUITY"}})
    def boom(tks):
        raise AssertionError("_sa_quotes must not be called when yahoo works")
    monkeypatch.setattr(src, "_sa_quotes", boom)
    monkeypatch.setattr(src, "_watchers", lambda tks: {
        "AAMI": {"watchlist_count": 15, "exchange": "NYSE"}})
    assert [c.ticker for c in src.fetch_candidates()] == ["AAMI"]


def test_fetch_candidates_raises_when_all_quote_sources_empty(monkeypatch):
    import pytest
    from src.source.base import SourceError
    src = RSSource()
    monkeypatch.setattr(src, "_wsj_universe", lambda: [("AAMI", "Acadian Inc.")])
    monkeypatch.setattr(src, "_yahoo_quotes", lambda tks: {})
    monkeypatch.setattr(src, "_sa_quotes", lambda tks: {})
    with pytest.raises(SourceError, match="quote"):
        src.fetch_candidates()
