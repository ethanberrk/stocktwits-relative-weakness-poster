import urllib.error
from src import stocktwits
from src.source.base import Candidate


def _c(ticker):
    return Candidate(ticker=ticker, name="x", exchange="NYSE", price=1.0,
                     pct_change_today=0.0, market_cap=2e9, week52_high=1.0,
                     security_type="EQUITY", watchers=1)


def test_st_symbol_maps_dash_to_dot():
    assert stocktwits.st_symbol("BRK-B") == "BRK.B"
    assert stocktwits.st_symbol("AAPL") == "AAPL"


def test_symbol_exists_true_on_200(monkeypatch):
    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(stocktwits.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert stocktwits.symbol_exists(_c("AAPL")) is True


def test_symbol_exists_false_on_404(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)
    monkeypatch.setattr(stocktwits.urllib.request, "urlopen", boom)
    assert stocktwits.symbol_exists(_c("NOPE")) is False


def test_symbol_exists_allows_on_403(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 403, "blocked", {}, None)
    monkeypatch.setattr(stocktwits.urllib.request, "urlopen", boom)
    assert stocktwits.symbol_exists(_c("AAPL")) is True
