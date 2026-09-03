"""Relative-Weakness source on Xignite (Ethan's licensed subscription).

Universe: Nasdaq Trader symbol directories (Nasdaq + NYSE/NYSE American,
          keyless, official, ETFs and test issues excluded).
Quotes:   GlobalQuotes delayed — Low/Low52Weeks/Last/%chg/exchange/name.
Mcap:     FactSet fundamentals, fetched ONLY for names that pass the 52wk test.
Watchers: Stocktwits public streams endpoint (the ranking axis), hits only.
Keep:     traded today, exchange in NYSE/NASDAQ/AMEX, common equity by
          name+symbol shape, market cap >= $1B, watcher count present.
          MIN_WATCHERS is applied in select, not here (same as the WSJ source).
"""
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from src import xignite
from src.fetch import get_json
from src.source.base import Candidate, LowsSource, SourceError

_PLAIN = re.compile(r"^[A-Z]{1,5}$")
_CLASS = re.compile(r"^[A-Z]{1,5}\.([A-Z])$")    # BRK.B / BF.A share classes


def canonical_ticker(act_symbol: str) -> str | None:
    """Nasdaq Trader symbol -> the dash form used everywhere in this repo
    (state files, cooldown, cashtag mapping): BRK.B -> BRK-B. Preferreds
    (BAC$B), units/warrants/rights suffixes (AAC.U/.W/.R) and 5-letter
    Nasdaq W/R/U shapes return None."""
    sym = (act_symbol or "").strip()
    if _PLAIN.match(sym):
        return None if config.WARRANT_RE.search(sym) else sym
    m = _CLASS.match(sym)
    if m and m.group(1) not in ("U", "W", "R"):
        return sym.replace(".", "-")
    return None


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": config.STOCKTWITS_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _rows(text: str) -> list[dict]:
    lines = [l for l in text.splitlines() if "|" in l and not l.startswith("File Creation")]
    if not lines:
        return []
    head = lines[0].split("|")
    return [dict(zip(head, l.split("|"))) for l in lines[1:]]


def listed_universe(fetch=_fetch_text) -> list[tuple[str, str]]:
    """[(ticker, name)] of US exchange-listed common equity (incl. ADRs),
    from Nasdaq Trader's nasdaqlisted + otherlisted files."""
    seen, pairs = set(), []

    def add(sym, name):
        tk = canonical_ticker(sym)
        if tk is None or tk in seen or config.NAME_EXCLUDE_RE.search(name):
            return
        seen.add(tk)
        pairs.append((tk, name))

    for r in _rows(fetch(config.NASDAQ_LISTED_URL)):
        if r.get("ETF") == "N" and r.get("Test Issue") == "N":
            add(r.get("Symbol"), r.get("Security Name", ""))
    for r in _rows(fetch(config.OTHER_LISTED_URL)):
        if (r.get("Exchange") in config.OTHER_LISTED_EXCHANGES
                and r.get("ETF") == "N" and r.get("Test Issue") == "N"):
            add(r.get("ACT Symbol"), r.get("Security Name", ""))
    if len(pairs) < config.MIN_UNIVERSE_SIZE:
        raise SourceError(f"listed universe has only {len(pairs)} names; "
                          "Nasdaq Trader symbol files look broken")
    return pairs


def is_new_low(q: dict, today) -> bool:
    """Day-cumulative test on a delayed quote: traded today AND today's low
    touched the 52-week low (Xignite's 52wk figure already includes today)."""
    if xignite.parse_xig_date(q.get("Date")) != today:
        return False
    lo, lo52 = q.get("Low") or 0, q.get("Low52Weeks") or 0
    return lo > 0 and lo52 > 0 and lo <= lo52 + 1e-6


def watchers(tickers: list[str]) -> dict[str, int | None]:
    """Stocktwits watchlist_count per ticker (public endpoint, 8 threads).
    Missing/indeterminate -> None (the candidate is then dropped)."""
    def one(tk):
        d = get_json(config.STOCKTWITS_SYMBOL_URL.format(symbol=tk.replace("-", ".")))
        sym = (d or {}).get("symbol") or {}
        return tk, sym.get("watchlist_count")
    out = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(one, t) for t in tickers]):
            tk, wc = fut.result()
            out[tk] = wc
    return out


def build_candidate(ticker: str, sec_name: str, q: dict, mcap, wc) -> Candidate | None:
    sec = q.get("Security") or {}
    exchange = sec.get("Market")
    if exchange not in config.XIGNITE_EXCHANGES:
        return None
    name = sec.get("Name") or sec_name
    if config.NAME_EXCLUDE_RE.search(name):
        return None
    if not mcap or mcap < config.MIN_MARKET_CAP:
        return None
    if wc is None:                                  # need a ranking axis
        return None
    if not q.get("Last"):
        return None
    return Candidate(
        ticker=ticker,
        name=name,
        exchange=exchange,
        price=float(q["Last"]),
        pct_change_today=float(q.get("PercentChangeFromPreviousClose") or 0.0),
        market_cap=float(mcap),
        week52_low=float(q["Low52Weeks"]),
        security_type="EQUITY",
        watchers=int(wc),
    )


class XigniteSource(LowsSource):
    def __init__(self, universe=listed_universe, watchers_fn=watchers):
        self._universe = universe
        self._watchers = watchers_fn

    def fetch_candidates(self) -> list[Candidate]:
        pairs = self._universe()
        names = dict(pairs)
        tickers = [t for t, _ in pairs]
        quotes = xignite.quotes(tickers)
        if not quotes:
            raise SourceError("Xignite returned zero quotes for the universe; feed looks broken")
        today = datetime.now(ZoneInfo(config.MARKET_TZ)).date()
        hits = [t for t in tickers if t in quotes and is_new_low(quotes[t], today)]
        caps = xignite.market_caps(hits) if hits else {}
        big = [t for t in hits if caps.get(t, 0) >= config.MIN_MARKET_CAP]
        watch = self._watchers(big) if big else {}
        out = []
        for t in big:
            c = build_candidate(t, names[t], quotes[t], caps.get(t), watch.get(t))
            if c is not None:
                out.append(c)
        return out
