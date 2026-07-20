import config


def test_min_market_cap_is_one_billion():
    assert config.MIN_MARKET_CAP == 1_000_000_000


def test_default_caps():
    assert config.MAX_PER_TICK == 2
    assert config.MAX_PER_DAY == 20


def test_wsj_url_present():
    assert "newfiftytwoweekhighsandlows" in config.WSJ_MDC_URL


def test_name_exclude_matches_etf_and_acquisition():
    assert config.NAME_EXCLUDE_RE.search("Some ETF")
    assert config.NAME_EXCLUDE_RE.search("Foo Acquisition Corp")
    assert not config.NAME_EXCLUDE_RE.search("Acadian Asset Management Inc.")


def test_stockanalysis_urls_present():
    assert "stockanalysis.com/api/quotes/s/" in config.SA_QUOTE_URL
    assert "{ticker}" in config.SA_QUOTE_URL
    assert "__data.json" in config.SA_PAGE_DATA_URL
    assert "{ticker_lower}" in config.SA_PAGE_DATA_URL
    assert "history" in config.SA_HISTORY_URL
    assert "{ticker}" in config.SA_HISTORY_URL


def test_chart_dimensions():
    assert config.CHART_WIDTH == 800
    assert config.CHART_HEIGHT == 450
