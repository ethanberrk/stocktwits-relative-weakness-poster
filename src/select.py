from datetime import date

import config
from src import state
from src.source.base import Candidate


class ValidationError(Exception):
    """Feed output looks broken; abort the tick before posting anything."""


def validate(candidates: list[Candidate]) -> None:
    if len(candidates) > config.MAX_PLAUSIBLE_LOWS:
        raise ValidationError(
            f"{len(candidates)} '52-week lows' is implausible "
            f"(gate: {config.MAX_PLAUSIBLE_LOWS}); refusing to post")


def ranked_eligible(candidates: list[Candidate], posted: list[dict],
                    today: date) -> list[Candidate]:
    """All postable candidates, MOST watchers first. Not capped —
    run.py walks this list and stops once it has enough that actually chart,
    so an un-chartable most-watched name can't starve the whole tick."""
    eligible = [c for c in candidates
                if c.market_cap >= config.MIN_MARKET_CAP
                and c.watchers >= config.MIN_WATCHERS
                and not state.is_blocked(c.ticker, posted, today)]
    eligible.sort(key=lambda c: c.watchers, reverse=True)
    return eligible


def slot_count(posted: list[dict], today: date) -> int:
    """How many posts this tick may still make: bounded by the per-tick cap
    and the day's remaining budget."""
    remaining_today = config.MAX_PER_DAY - state.daily_count(posted, today)
    return max(0, min(config.MAX_PER_TICK, remaining_today))
