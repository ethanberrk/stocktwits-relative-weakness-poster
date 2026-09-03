"""All knobs in one place. Nothing else defines numbers or thresholds."""
import os
import re
import urllib.parse

MIN_MARKET_CAP = 1_000_000_000          # USD floor (>= applied in source + select)
MIN_WATCHERS = 5_000                    # "crowded breakdown" needs a crowd:
                                        # ~1,000 watchers is baseline for an
                                        # anonymous $10B mid-cap (PNR 973,
                                        # WTS 422 on 2026-07-22), so the
                                        # signal floor sits well above it
MAX_PER_TICK = int(os.environ.get("MAX_PER_TICK", "2"))   # posts per 30-min tick
MAX_PER_DAY = int(os.environ.get("MAX_PER_DAY", "20"))    # posts per trading day
MAX_PLAUSIBLE_LOWS = 2000               # broken-feed gate. Looser than the RS
                                        # poster's 500: new lows legitimately
                                        # run to four digits on selloff days,
                                        # and those are the best content days.
                                        # Caps control volume, not this gate.
MIN_HISTORY_DAYS = 330                  # skip recent IPOs: a "1Y" chart needs
                                        # ~a year of candles (330 = slack for
                                        # names barely a year old)

MARKET_TZ = "America/New_York"
MARKET_OPEN = (9, 30)                   # ET
MARKET_CLOSE = (16, 0)                  # ET

# Charts are rendered in-process (src/chart.py, matplotlib) from
# stockanalysis.com daily history — no chart API or key involved.
CHART_WIDTH = 800
CHART_HEIGHT = 450

# stockanalysis.com: keyless quote/market-cap/history source. Primary for
# charts; fallback for the quote stage when Yahoo rate-limits (it 429s
# datacenter IPs, which silently zeroed out every candidate on 2026-07-09).
SA_QUOTE_URL = "https://stockanalysis.com/api/quotes/s/{ticker}"
SA_PAGE_DATA_URL = "https://stockanalysis.com/stocks/{ticker_lower}/__data.json"
SA_HISTORY_URL = ("https://stockanalysis.com/api/symbol/s/{ticker}/history"
                  "?range=1Y&period=Daily")
STOCKTWITS_SYMBOL_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
STOCKTWITS_CREATE_URL = "https://api.stocktwits.com/api/2/messages/create.json"
STOCKTWITS_USER_AGENT = "stocktwits-relative-weakness-poster/1.0"

# WSJ Market Data Center async feed carries both new 52-week highs and lows
# (refreshes ~5 min); this repo reads the lows side.
WSJ_MDC_URL = ("https://www.wsj.com/market-data/stocks/newfiftytwoweekhighsandlows?id="
               + urllib.parse.quote('{"application":"WSJ","refreshInterval":300000}')
               + "&type=mdc_fiftytwoweek")

# Drop non-common-equity by name (same rule the WSJ prototype proved out).
NAME_EXCLUDE_RE = re.compile(
    r"\b(ETF|Fund|Pfd|Preferred|Notes?|Units?|Un|Warrants?|Wt|Bond|Rt|Rights)\b"
    r"|Acquisition Corp",
    re.I,
)

# ---------------------------------------------------------------------------
# Data-source switch. "legacy" = the scraped feeds above (WSJ lows list +
# Yahoo/stockanalysis quotes + stockanalysis.com charts); "xignite" = Ethan's licensed Xignite subscription
# (SEC ticker list for the universe, GlobalQuotes for the 52wk-low test,
# FactSet fundamentals for market cap, GlobalHistorical for charts).
# In CI this is the repository VARIABLE `DATA_SOURCE` (tick.yml), so going
# live — and reverting — is a Settings change, not a deploy. Design:
# docs/superpowers/specs/2026-09-03-xignite-data-source-design.md
DATA_SOURCE = os.environ.get("DATA_SOURCE", "legacy")
DATA_SOURCES = ("legacy", "xignite")
XIGNITE_TOKEN = os.environ.get("XIGNITE_TOKEN", "")
XIGNITE_QUOTES_URL = ("https://globalquotes.xignite.com/v3/xGlobalQuotes.json/"
                      "GetGlobalDelayedQuotes")
XIGNITE_HISTORY_URL = ("https://globalhistorical.xignite.com/v3/xGlobalHistorical.json/"
                       "GetGlobalHistoricalQuotesRange")
XIGNITE_FUNDAMENTALS_URL = ("https://factsetfundamentals.xignite.com/"
                            "xFactSetFundamentals.json/GetFundamentals")
XIGNITE_BATCH = 500                     # identifiers per call (verified 2026-09-03)
XIGNITE_HISTORY_DAYS = 400              # calendar days requested for a "1Y" chart
XIGNITE_EXCHANGES = ("NYSE", "NASDAQ", "AMEX")   # Security.Market values kept

# Universe for the xignite source: Nasdaq Trader's official symbol
# directories (keyless; refreshed nightly). nasdaqlisted.txt = Nasdaq;
# otherlisted.txt = every other US exchange, filtered to NYSE (N) and NYSE
# American (A) — Arca/BATS/IEX are ETF venues. ETF and test issues dropped.
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
OTHER_LISTED_EXCHANGES = ("N", "A")
MIN_UNIVERSE_SIZE = 1000                # tripwire: fewer listed names = broken files
# Preferreds / warrants / rights / units by symbol shape (same rules the
# 52wk-lows poster proved live 2026-07-27). Dual-class lines (BRK-B, BF-B) survive.
PREFERRED_RE = re.compile(r"-P[A-Z]?$")
WARRANT_RE = re.compile(r"^[A-Z]{4}(W|R|U)$|-(WT|RT|UN|W|R|U)$")

# Shadow comparison output (see scripts/shadow.py)
SHADOW_DIR = "shadow"
