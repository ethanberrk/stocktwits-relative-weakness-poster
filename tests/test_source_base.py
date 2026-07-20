import dataclasses
import pytest
from src.source.base import Candidate, HighsSource, SourceError


def _candidate(**over):
    base = dict(ticker="ABCD", name="Abcd Inc.", exchange="NASDAQ", price=10.0,
                pct_change_today=1.5, market_cap=2e9, week52_high=10.5,
                security_type="EQUITY", watchers=42)
    base.update(over)
    return Candidate(**base)


def test_candidate_carries_watchers():
    c = _candidate(watchers=7)
    assert c.watchers == 7


def test_candidate_is_frozen():
    c = _candidate()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.watchers = 9


def test_source_is_abstract():
    with pytest.raises(TypeError):
        HighsSource()
    assert issubclass(SourceError, Exception)
