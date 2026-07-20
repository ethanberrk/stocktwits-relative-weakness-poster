"""Relative-Strength source: WSJ new-52wk-highs universe, ranked-later by
watchers. Ported from stocktwits-relative-strength/fetch_wsj.py.

Universe:  WSJ Market Data Center "New 52 Week Highs" feed.
Enrich:    Yahoo v7 bulk quote (cookie+crumb) — mcap/price/%chg/52wk high/type.
           Falls back to stockanalysis.com per-ticker (keyless) when Yahoo
           returns nothing: Yahoo 429s datacenter IPs (incl. GitHub runners),
           which on 2026-07-09 silently zeroed out every candidate all day.
Watchers:  Stocktwits streams endpoint (the ranking axis) + exchange.
Keep:      market_cap > $1B, watcher count present, chart-resolvable exchange.

urllib on purpose (see src/stocktwits.py): Stocktwits' CDN 403s the requests
TLS fingerprint but passes urllib; the WSJ prototype relied on the same.
"""
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from src.fetch import _UA, get_json
from src.source.base import Candidate, HighsSource, SourceError

# Stocktwits exchange string -> TradingView prefix the chart renderer shows.
# Anything not here can't be charted reliably, so the row is dropped.
_EXCHANGE_PREFIX = {
    "NYSE": "NYSE",
    "NASDAQ": "NASDAQ",
    "NYSEAmerican": "AMEX",
    "NYSEArca": "AMEX",
    "AMEX": "AMEX",
    "BATS": "BATS",
}

_ABBREV_RE = re.compile(r"^([\d.]+)([KMBT])$")
_ABBREV_MULT = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _parse_abbrev_number(v):
    """'5.38B' -> 5.38e9; plain numbers pass through; anything else -> None."""
    if isinstance(v, (int, float)):
        return float(v)
    m = _ABBREV_RE.match(str(v or "").replace(",", "").strip())
    return float(m.group(1)) * _ABBREV_MULT[m.group(2)] if m else None


def _build_candidate(ticker: str, name: str, quote: dict,
                     watch: dict) -> Candidate | None:
    mcap = (quote or {}).get("marketCap")
    wc = (watch or {}).get("watchlist_count")
    prefix = _EXCHANGE_PREFIX.get((watch or {}).get("exchange"))
    price = (quote or {}).get("regularMarketPrice")
    if not mcap or mcap < config.MIN_MARKET_CAP:    # >= $1B, matches select.pick
        return None
    if wc is None:                                  # need a ranking axis
        return None
    if prefix is None:                              # can't chart it
        return None
    if not price:
        return None
    return Candidate(
        ticker=ticker,
        name=name,
        exchange=prefix,
        price=float(price),
        pct_change_today=float(quote.get("regularMarketChangePercent") or 0.0),
        market_cap=float(mcap),
        week52_high=float(quote.get("fiftyTwoWeekHigh") or 0.0),
        security_type=quote.get("quoteType") or "",
        watchers=int(wc),
    )


class RSSource(HighsSource):
    def _wsj_universe(self) -> list[tuple[str, str]]:
        d = get_json(config.WSJ_MDC_URL)
        data = (d or {}).get("data") or {}
        seen, pairs = set(), []
        for _section, payload in data.items():
            if not isinstance(payload, dict):
                continue
            for r in payload.get("highs") or []:
                tk = (r.get("ticker") or "").strip()
                nm = (r.get("name") or "").strip()
                if not tk or tk in seen:
                    continue
                if "." in tk or config.NAME_EXCLUDE_RE.search(nm):
                    continue
                seen.add(tk)
                pairs.append((tk, nm))
        return pairs

    def _yahoo_quotes(self, tickers: list[str]) -> dict:
        # cookie then crumb
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        try:
            opener.open(urllib.request.Request(
                "https://fc.yahoo.com", headers={"User-Agent": _UA}), timeout=12)
        except Exception:
            pass
        try:
            crumb = opener.open(urllib.request.Request(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                headers={"User-Agent": _UA}), timeout=12).read().decode()
        except Exception:
            return {}
        out = {}
        for i in range(0, len(tickers), 40):
            chunk = tickers[i:i + 40]
            url = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols="
                   + ",".join(chunk) + "&crumb=" + urllib.parse.quote(crumb))
            d = get_json(url, opener=opener)
            for q in ((d or {}).get("quoteResponse", {}) or {}).get("result", []) or []:
                out[q.get("symbol")] = q
        return out

    def _sa_quotes(self, tickers: list[str]) -> dict:
        """stockanalysis.com fallback, shaped like the Yahoo v7 result so
        _build_candidate needs no branching. Two keyless requests per ticker:
        the quote API (price/%chg/52wk high) and the stock page's SvelteKit
        __data.json (market cap, encoded as key->index into a values array)."""
        def one(tk):
            q = (get_json(config.SA_QUOTE_URL.format(ticker=tk)) or {}).get("data")
            if not q or not q.get("p"):
                return tk, None
            mcap = None
            page = get_json(config.SA_PAGE_DATA_URL.format(ticker_lower=tk.lower()))
            for node in (page or {}).get("nodes") or []:
                if not isinstance(node, dict) or node.get("type") != "data":
                    continue
                data = node.get("data") or []
                for item in data:
                    if isinstance(item, dict) and "marketCap" in item:
                        mcap = _parse_abbrev_number(data[item["marketCap"]])
            if mcap is None:
                return tk, None
            return tk, {"marketCap": mcap,
                        "regularMarketPrice": float(q["p"]),
                        "regularMarketChangePercent": float(q.get("cp") or 0.0),
                        "fiftyTwoWeekHigh": float(q.get("h52") or 0.0),
                        "quoteType": "EQUITY"}
        out = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            for fut in as_completed([ex.submit(one, t) for t in tickers]):
                tk, quote = fut.result()
                if quote is not None:
                    out[tk] = quote
        return out

    def _watchers(self, tickers: list[str]) -> dict:
        def one(tk):
            d = get_json(config.STOCKTWITS_SYMBOL_URL.format(symbol=tk))
            sym = (d or {}).get("symbol") or {}
            return tk, ({"watchlist_count": sym.get("watchlist_count"),
                         "exchange": sym.get("exchange")} if sym else {})
        out = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            for fut in as_completed([ex.submit(one, t) for t in tickers]):
                tk, info = fut.result()
                out[tk] = info
        return out

    def fetch_candidates(self) -> list[Candidate]:
        pairs = self._wsj_universe()
        if not pairs:
            raise SourceError("WSJ feed returned zero new highs; feed looks broken")
        names = {t: n for t, n in pairs}
        tickers = [t for t, _ in pairs]
        quotes = self._yahoo_quotes(tickers)
        if not quotes:
            quotes = self._sa_quotes(tickers)
        if not quotes:
            # Tripwire: a non-empty universe with zero quotes means the quote
            # stage is broken, not a quiet day. Fail the tick red — the
            # 2026-07-09 Yahoo 429 outage ran all day as green no-op ticks.
            raise SourceError(
                f"{len(pairs)} names on the WSJ list but every quote source "
                "returned nothing; quote enrichment looks broken")
        watch = self._watchers(tickers)
        out = []
        for tk in tickers:
            c = _build_candidate(tk, names[tk], quotes.get(tk) or {}, watch.get(tk) or {})
            if c is not None:
                out.append(c)
        return out
