"""
MFS Equity Research Associate — Cowork domain-expert plugin (MCP server).

Persona: the equity research associate on the MFS research platform. Reasons
about company fundamentals, consensus estimates, earnings surprises and the
variance-to-estimate that drives a model refresh and thesis check.

DATA: REAL market data via FinnHub (free tier). Set FINNHUB_API_KEY in the
environment or in data/.env. News/profile/fundamentals/estimates are live.
Run: python servers/equity_server.py   (stdio transport)
"""
import os
import sys
import time
import requests
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))

# load key from env or a local .env (simple parser, no extra deps)
def _load_key():
    k = os.environ.get("FINNHUB_API_KEY")
    if k:
        return k.strip()
    envp = os.path.join(HERE, "..", "data", ".env")
    if os.path.exists(envp):
        for line in open(envp, encoding="utf-8"):
            line = line.strip()
            if line.startswith("FINNHUB_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

API_KEY = _load_key()
BASE = "https://finnhub.io/api/v1"

sys.path.insert(0, os.path.join(HERE, "..", "shared"))
try:
    from universe import UNIVERSE
except Exception:
    UNIVERSE = {}

mcp = FastMCP("MFS Equity Research Associate")

_cache = {}
_CACHE_TTL = 300


def _get(path, params):
    if not API_KEY:
        return {"_error": "FINNHUB_API_KEY not set. Add it to data/.env or the environment."}
    params = dict(params)
    params["token"] = API_KEY
    key = path + str(sorted(params.items()))
    now = time.time()
    if key in _cache and now - _cache[key][0] < _CACHE_TTL:
        return _cache[key][1]
    try:
        r = requests.get(f"{BASE}{path}", params=params, timeout=15)
        if r.status_code == 429:
            return {"_error": "FinnHub rate limit hit (free tier: 60/min). Wait a moment."}
        r.raise_for_status()
        data = r.json()
        _cache[key] = (now, data)
        return data
    except Exception as e:
        return {"_error": f"FinnHub request failed: {e}"}


@mcp.tool()
def search_company(query: str) -> dict:
    """Search for a company/symbol by name or ticker. Returns matching symbols
    with description. Real FinnHub data."""
    data = _get("/search", {"q": query})
    if isinstance(data, dict) and data.get("_error"):
        return data
    results = [{"symbol": r.get("symbol"), "description": r.get("description"),
                "type": r.get("type")} for r in data.get("result", [])[:10]]
    return {"query": query, "count": len(results), "results": results}


@mcp.tool()
def get_company_profile(ticker: str) -> dict:
    """Get the company profile: name, exchange, industry, market cap, shares
    outstanding, country, website. Real FinnHub data."""
    data = _get("/stock/profile2", {"symbol": ticker.upper()})
    if isinstance(data, dict) and data.get("_error"):
        return data
    if not data:
        return {"error": f"No profile for {ticker}"}
    return {
        "ticker": ticker.upper(), "name": data.get("name"),
        "exchange": data.get("exchange"), "industry": data.get("finnhubIndustry"),
        "market_cap_usd_mm": data.get("marketCapitalization"),
        "shares_outstanding_mm": data.get("shareOutstanding"),
        "country": data.get("country"), "currency": data.get("currency"),
        "ipo": data.get("ipo"), "website": data.get("weburl"),
    }


@mcp.tool()
def get_quote(ticker: str) -> dict:
    """Get the current price quote: last, change, % change, day high/low, prior
    close. Real FinnHub data."""
    data = _get("/quote", {"symbol": ticker.upper()})
    if isinstance(data, dict) and data.get("_error"):
        return data
    return {
        "ticker": ticker.upper(), "current_price": data.get("c"),
        "change": data.get("d"), "percent_change": data.get("dp"),
        "high": data.get("h"), "low": data.get("l"),
        "open": data.get("o"), "prev_close": data.get("pc"),
    }


@mcp.tool()
def get_fundamentals(ticker: str) -> dict:
    """Get key fundamental metrics: valuation (P/E, P/B, P/S), margins, growth,
    returns (ROE/ROA), 52-week range, beta. Real FinnHub 'metric' data."""
    data = _get("/stock/metric", {"symbol": ticker.upper(), "metric": "all"})
    if isinstance(data, dict) and data.get("_error"):
        return data
    m = data.get("metric", {}) if isinstance(data, dict) else {}
    if not m:
        return {"error": f"No fundamentals for {ticker}"}
    return {
        "ticker": ticker.upper(),
        "pe_ttm": m.get("peTTM"), "pb": m.get("pbQuarterly"), "ps_ttm": m.get("psTTM"),
        "ev_ebitda": m.get("currentEv/freeCashFlowTTM"),
        "gross_margin_ttm": m.get("grossMarginTTM"),
        "net_margin_ttm": m.get("netProfitMarginTTM"),
        "operating_margin_ttm": m.get("operatingMarginTTM"),
        "roe_ttm": m.get("roeTTM"), "roa_ttm": m.get("roaTTM"),
        "revenue_growth_ttm_yoy": m.get("revenueGrowthTTMYoy"),
        "eps_growth_ttm_yoy": m.get("epsGrowthTTMYoy"),
        "debt_to_equity": m.get("totalDebt/totalEquityQuarterly"),
        "current_ratio": m.get("currentRatioQuarterly"),
        "52w_high": m.get("52WeekHigh"), "52w_low": m.get("52WeekLow"),
        "beta": m.get("beta"), "dividend_yield": m.get("dividendYieldIndicatedAnnual"),
    }


@mcp.tool()
def get_estimates(ticker: str) -> dict:
    """Get consensus analyst recommendation trends (strong buy/buy/hold/sell/strong
    sell) for the most recent periods. Real FinnHub data."""
    data = _get("/stock/recommendation", {"symbol": ticker.upper()})
    if isinstance(data, dict) and data.get("_error"):
        return data
    if not data:
        return {"error": f"No estimates for {ticker}"}
    rows = data[:4] if isinstance(data, list) else []
    return {
        "ticker": ticker.upper(),
        "recommendation_trends": [
            {"period": r.get("period"), "strong_buy": r.get("strongBuy"),
             "buy": r.get("buy"), "hold": r.get("hold"), "sell": r.get("sell"),
             "strong_sell": r.get("strongSell")} for r in rows],
    }


@mcp.tool()
def get_price_target(ticker: str) -> dict:
    """Get the consensus analyst price target (high/low/median/mean) versus the
    current price. Real FinnHub data (may require a paid tier for some symbols)."""
    data = _get("/stock/price-target", {"symbol": ticker.upper()})
    if isinstance(data, dict) and data.get("_error"):
        return data
    if not data or not data.get("targetMean"):
        return {"ticker": ticker.upper(),
                "note": "No price-target data available on the current FinnHub tier for this symbol."}
    return {
        "ticker": ticker.upper(),
        "target_high": data.get("targetHigh"), "target_low": data.get("targetLow"),
        "target_mean": data.get("targetMean"), "target_median": data.get("targetMedian"),
        "last_updated": data.get("lastUpdated"),
    }


@mcp.tool()
def get_earnings_surprises(ticker: str) -> dict:
    """Get the recent quarterly earnings surprise history: actual vs. estimated EPS
    and the surprise/beat-miss for each of the last four quarters. Real FinnHub data."""
    data = _get("/stock/earnings", {"symbol": ticker.upper()})
    if isinstance(data, dict) and data.get("_error"):
        return data
    if not data:
        return {"error": f"No earnings data for {ticker}"}
    rows = data[:4] if isinstance(data, list) else []
    out = []
    for r in rows:
        actual, est = r.get("actual"), r.get("estimate")
        surprise_pct = None
        if actual is not None and est not in (None, 0):
            surprise_pct = round((actual - est) / abs(est) * 100, 1)
        out.append({"period": r.get("period"), "actual_eps": actual,
                    "estimate_eps": est, "surprise": r.get("surprise"),
                    "surprise_pct": surprise_pct,
                    "beat_miss": ("Beat" if surprise_pct and surprise_pct > 0
                                  else "Miss" if surprise_pct and surprise_pct < 0 else "In line")})
    return {"ticker": ticker.upper(), "earnings_surprises": out}


@mcp.tool()
def get_news(ticker: str, days: int = 14) -> dict:
    """Get recent company news headlines over the last N days (default 14). Real
    FinnHub data."""
    import datetime as dt
    to = dt.date.today()
    frm = to - dt.timedelta(days=days)
    data = _get("/company-news", {"symbol": ticker.upper(),
                                  "from": frm.isoformat(), "to": to.isoformat()})
    if isinstance(data, dict) and data.get("_error"):
        return data
    rows = data[:12] if isinstance(data, list) else []
    news = [{"datetime": __import__("datetime").datetime.fromtimestamp(r.get("datetime", 0)).isoformat(),
             "headline": r.get("headline"), "source": r.get("source"),
             "summary": (r.get("summary") or "")[:280], "url": r.get("url")} for r in rows]
    return {"ticker": ticker.upper(), "days": days, "count": len(news), "news": news}


@mcp.tool()
def run_variance_analysis(ticker: str) -> dict:
    """Run a variance-to-estimate read for a name that just reported: pull the latest
    earnings surprise, the consensus recommendation trend, valuation context and
    recent price reaction, and summarise what an MFS analyst should focus on. Real
    FinnHub data, assembled."""
    prof = get_company_profile(ticker)
    quote = get_quote(ticker)
    surp = get_earnings_surprises(ticker)
    fund = get_fundamentals(ticker)
    rec = get_estimates(ticker)

    for d in (prof, quote, surp, fund, rec):
        if isinstance(d, dict) and d.get("_error"):
            return d

    latest = (surp.get("earnings_surprises") or [{}])[0]
    focus = []
    sp = latest.get("surprise_pct")
    if sp is not None:
        focus.append(f"Latest quarter EPS {latest.get('beat_miss','').lower()} by {sp}% "
                     f"(actual {latest.get('actual_eps')} vs est {latest.get('estimate_eps')}).")
    if quote.get("percent_change") is not None:
        focus.append(f"Stock is {quote.get('percent_change')}% on the day at {quote.get('current_price')}.")
    pe = fund.get("pe_ttm")
    if pe:
        focus.append(f"Trades at {round(pe,1)}x trailing earnings; net margin {fund.get('net_margin_ttm')}%.")
    rg = fund.get("revenue_growth_ttm_yoy")
    if rg is not None:
        focus.append(f"Revenue growth {rg}% YoY, EPS growth {fund.get('eps_growth_ttm_yoy')}% YoY.")
    trends = rec.get("recommendation_trends") or []
    if trends:
        t0 = trends[0]
        focus.append(f"Consensus: {t0.get('strong_buy',0)+t0.get('buy',0)} buy / "
                     f"{t0.get('hold',0)} hold / {t0.get('sell',0)+t0.get('strong_sell',0)} sell "
                     f"({t0.get('period')}).")

    return {
        "ticker": ticker.upper(),
        "company": prof.get("name"),
        "variance_read": focus,
        "analyst_summary": (f"{prof.get('name')} ({ticker.upper()}): " + " ".join(focus)
                            if focus else "Insufficient data for a variance read."),
        "data_source": "FinnHub (real market data)",
    }


if __name__ == "__main__":
    mcp.run()
