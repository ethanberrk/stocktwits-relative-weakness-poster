from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.source.base import Candidate
from src.stocktwits import st_symbol


@dataclass(frozen=True)
class PostResult:
    post_id: str | None
    dry_run: bool


class Publisher(ABC):
    @abstractmethod
    def post(self, candidate: Candidate, text: str, image_png: bytes) -> PostResult: ...


def compose_post_text(c: Candidate) -> str:
    # No price/%chg/mcap in the copy: those go stale between the tick and the
    # reader; the attached chart carries the quantitative story. Watcher count
    # is stable enough to include and is the whole point of this feed.
    # Cashtag uses Stocktwits symbology (BRK.B, not Yahoo's BRK-B).
    return f"${st_symbol(c.ticker)} undiscovered breakout with {c.watchers} watchers"
