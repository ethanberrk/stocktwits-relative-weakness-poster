import json
from datetime import date

import pytest

from src.publish.base import compose_post_text, PostResult
from src.publish.dryrun import DryRunPublisher
from src.publish import stocktwits_pub
from src.publish.stocktwits_pub import StocktwitsPublisher, PublishError
from src.source.base import Candidate


def _c(ticker="ABCD", watchers=9):
    return Candidate(ticker=ticker, name="x", exchange="NASDAQ", price=1.0,
                     pct_change_today=0.0, market_cap=2e9, week52_high=1.0,
                     security_type="EQUITY", watchers=watchers)


def test_compose_post_text_exact():
    assert compose_post_text(_c("AAMI", 15)) == \
        "$AAMI undiscovered breakout with 15 watchers"


def test_compose_post_text_uses_stocktwits_symbology():
    assert compose_post_text(_c("BRK-B", 100)) == \
        "$BRK.B undiscovered breakout with 100 watchers"


def test_dryrun_writes_artifacts_and_returns_dry_result(tmp_path):
    pub = DryRunPublisher(tmp_path, date(2026, 7, 8))
    res = pub.post(_c("ABCD"), "hello", b"PNG")
    assert res == PostResult(post_id=None, dry_run=True)
    day = tmp_path / "2026-07-08"
    assert (day / "ABCD.png").read_bytes() == b"PNG"
    assert (day / "ABCD.txt").read_text() == "hello"


def test_stocktwits_publisher_success(tmp_path):
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({"response": {"status": 200},
                               "message": {"id": 555}}).encode()
    pub = StocktwitsPublisher("tok", tmp_path, date(2026, 7, 8),
                              urlopen=lambda *a, **k: Resp())
    res = pub.post(_c("ABCD"), "hello", b"PNG")
    assert res.post_id == "555" and res.dry_run is False
    assert (tmp_path / "2026-07-08" / "ABCD.png").read_bytes() == b"PNG"


def test_stocktwits_publisher_raises_on_error_status(tmp_path):
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({"response": {"status": 429}}).encode()
    pub = StocktwitsPublisher("tok", tmp_path, date(2026, 7, 8),
                              urlopen=lambda *a, **k: Resp())
    with pytest.raises(PublishError):
        pub.post(_c("ABCD"), "hello", b"PNG")
