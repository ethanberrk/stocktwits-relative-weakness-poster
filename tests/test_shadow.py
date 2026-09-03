"""scripts/shadow.py: diff the inactive source against the tick's dump."""
import json
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import shadow  # noqa: E402
import config  # noqa: E402
from src.source.base import Candidate, LowsSource  # noqa: E402


def cand(ticker, watchers=10_000):
    return Candidate(ticker, f"{ticker} Inc", "NYSE", 100.0, -2.0, 5e9, 99.0, "EQUITY", watchers)


def test_other_flips():
    assert shadow.other("legacy") == "xignite"
    assert shadow.other("xignite") == "legacy"


def test_compare_reports_overlap_and_replayed_picks(monkeypatch):
    monkeypatch.setattr(config, "MAX_PER_TICK", 2)
    r = shadow.compare("legacy", [cand("A", 90_000), cand("B", 50_000)],
                       "xignite", [cand("A", 90_000), cand("C", 20_000)], [], date(2026, 7, 1))
    assert r["counts"] == {"active": 2, "shadow": 2, "both": 1}
    assert r["only_in_active"] == ["B"] and r["only_in_shadow"] == ["C"]
    assert r["would_pick"] == {"legacy": ["A", "B"], "xignite": ["A", "C"]}
    assert r["picks_agree"] is False


def test_compare_applies_watcher_floor_like_the_tick():
    r = shadow.compare("legacy", [cand("A", 90_000), cand("Q", 10)],
                       "xignite", [cand("A", 90_000)], [], date(2026, 7, 1))
    assert r["would_pick"] == {"legacy": ["A"], "xignite": ["A"]}
    assert r["picks_agree"] is True


class Fake(LowsSource):
    def __init__(self, cands): self.cands = cands
    def fetch_candidates(self): return self.cands


def test_main_writes_diff_and_removes_dump(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_SOURCE", "legacy")
    monkeypatch.setattr(shadow, "build_source", lambda name: Fake([cand("A"), cand("Z")]))
    day = tmp_path / "shadow" / date.today().isoformat()
    day.mkdir(parents=True)
    from dataclasses import asdict
    (day / "1400.active.json").write_text(json.dumps(
        {"source": "legacy", "time": "t", "candidates": [asdict(cand("A"))]}))
    rc = shadow.main(["--force", "--shadow-dir", str(tmp_path / "shadow"),
                      "--state", str(tmp_path / "none.json")])
    assert rc == 0
    out = json.loads((day / "1400.json").read_text())
    assert out["shadow"] == "xignite" and out["only_in_shadow"] == ["Z"]
    assert not (day / "1400.active.json").exists()


def test_main_records_shadow_failure_without_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_SOURCE", "legacy")

    class Boom(LowsSource):
        def fetch_candidates(self): raise RuntimeError("no token")
    monkeypatch.setattr(shadow, "build_source", lambda name: Boom())
    rc = shadow.main(["--force", "--shadow-dir", str(tmp_path / "shadow"),
                      "--state", str(tmp_path / "none.json")])
    assert rc == 1
    files = list((tmp_path / "shadow").rglob("*.json"))
    assert len(files) == 1 and "no token" in json.loads(files[0].read_text())["error"]
