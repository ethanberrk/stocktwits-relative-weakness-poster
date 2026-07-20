"""All knobs in one place. Nothing else defines numbers or thresholds."""
import os
import re
import urllib.parse

MIN_MARKET_CAP = 1_000_000_000          # USD floor (>= applied in source + select)
MAX_PER_TICK = int(os.environ.get("MAX_PER_TICK", "2"))   # posts per 30-min tick
MAX_PER_DAY = int(os.environ.get("MAX_PER_DAY", "20"))    # posts per trading day
MAX_PLAUSIBLE_HIGHS = 500               # validation gate: more = broken feed
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
STOCKTWITS_USER_AGENT = "stocktwits-relative-strength-poster/1.0"

# WSJ Market Data Center async feed for New 52-Week Highs (refreshes ~5 min).
WSJ_MDC_URL = ("https://www.wsj.com/market-data/stocks/newfiftytwoweekhighsandlows?id="
               + urllib.parse.quote('{"application":"WSJ","refreshInterval":300000}')
               + "&type=mdc_fiftytwoweek")

# Drop non-common-equity by name (same rule the WSJ prototype proved out).
NAME_EXCLUDE_RE = re.compile(
    r"\b(ETF|Fund|Pfd|Preferred|Notes?|Units?|Un|Warrants?|Wt|Bond|Rt|Rights)\b"
    r"|Acquisition Corp",
    re.I,
)
