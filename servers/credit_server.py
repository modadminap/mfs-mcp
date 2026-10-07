"""
MFS Credit Analyst — Cowork domain-expert plugin (MCP server).

Persona: the fixed-income / credit analyst on the MFS research platform.
Reasons about issuer credit quality, rating trajectory, and downgrade risk.

DATA: 100% SYNTHETIC (data/credit.db), Moody's-style scale. Demo only.
Run: python servers/credit_server.py   (stdio transport)
"""
import os
import sqlite3
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "data", "credit.db")

mcp = FastMCP("MFS Credit Analyst")

MOODYS_SCALE = [
    "Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3",
    "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3",
    "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C",
]
_WM = "SYNTHETIC — demonstration data only, not Moody's."


def _con():
    return sqlite3.connect(DB)


@mcp.tool()
def get_issuer_rating(ticker: str) -> dict:
    """Get the current long-term issuer credit rating, outlook and watch status
    for a company by ticker. Synthetic Moody's-style scale (Aaa..C)."""
    con = _con()
    r = con.execute(
        "SELECT ticker,issuer,sector,lt_rating,grade,outlook,watch,last_action_date "
        "FROM issuer_ratings WHERE ticker=?", (ticker.upper(),)).fetchone()
    con.close()
    if not r:
        return {"error": f"No rating for {ticker}", "note": _WM}
    return {
        "ticker": r[0], "issuer": r[1], "sector": r[2],
        "long_term_rating": r[3], "grade": r[4], "outlook": r[5],
        "watch_status": r[6], "last_action_date": r[7], "_watermark": _WM,
    }


@mcp.tool()
def get_rating_actions(ticker: str) -> dict:
    """Get the historical rating-action trail (upgrades, downgrades, affirmations)
    for an issuer, oldest to newest, with the rationale for each."""
    con = _con()
    rows = con.execute(
        "SELECT action_date,action,from_rating,to_rating,rationale "
        "FROM rating_actions WHERE ticker=? ORDER BY action_date", (ticker.upper(),)).fetchall()
    con.close()
    actions = [{"date": a, "action": b, "from": c, "to": d, "rationale": e}
               for a, b, c, d, e in rows]
    return {"ticker": ticker.upper(), "actions": actions, "count": len(actions), "_watermark": _WM}


@mcp.tool()
def get_credit_metrics(ticker: str) -> dict:
    """Get quantitative credit metrics for an issuer: probability of default (1yr/5yr),
    LGD, recovery, leverage (debt/EBITDA), interest coverage, FFO/debt, and the
    model-implied (EDF) rating. Synthetic."""
    con = _con()
    r = con.execute(
        "SELECT pd_1yr,pd_5yr,lgd,recovery,debt_to_ebitda,interest_cov,ffo_to_debt,edf_implied_rating "
        "FROM credit_metrics WHERE ticker=?", (ticker.upper(),)).fetchone()
    con.close()
    if not r:
        return {"error": f"No metrics for {ticker}", "note": _WM}
    return {
        "ticker": ticker.upper(),
        "prob_default_1yr_pct": r[0], "prob_default_5yr_pct": r[1],
        "loss_given_default": r[2], "recovery_rate": r[3],
        "debt_to_ebitda": r[4], "interest_coverage": r[5], "ffo_to_debt": r[6],
        "model_implied_rating": r[7], "_watermark": _WM,
    }


@mcp.tool()
def screen_by_rating(min_rating: str = "Aaa", max_rating: str = "C",
                     sector: str = "") -> dict:
    """Screen the issuer universe for names whose rating falls between min_rating
    and max_rating (inclusive), optionally within a GICS sector. Returns issuers
    sorted best-to-worst credit."""
    try:
        lo = MOODYS_SCALE.index(min_rating)
        hi = MOODYS_SCALE.index(max_rating)
    except ValueError:
        return {"error": "Invalid rating. Use Moody's scale Aaa..C", "note": _WM}
    con = _con()
    q = ("SELECT ticker,issuer,sector,lt_rating,grade,outlook FROM issuer_ratings "
         "WHERE rating_idx BETWEEN ? AND ?")
    params = [lo, hi]
    if sector:
        q += " AND sector=?"
        params.append(sector)
    q += " ORDER BY rating_idx"
    rows = con.execute(q, params).fetchall()
    con.close()
    results = [{"ticker": a, "issuer": b, "sector": c, "rating": d,
                "grade": e, "outlook": f} for a, b, c, d, e, f in rows]
    return {"criteria": {"min": min_rating, "max": max_rating, "sector": sector or "all"},
            "count": len(results), "issuers": results, "_watermark": _WM}


@mcp.tool()
def assess_downgrade_risk(ticker: str) -> dict:
    """Assess downgrade risk for an issuer by combining its outlook, watch status,
    rating trajectory, model-implied (EDF) rating vs. current rating, and leverage.
    Returns a plain-language risk read for a credit analyst to judge."""
    con = _con()
    rr = con.execute(
        "SELECT issuer,lt_rating,rating_idx,outlook,watch FROM issuer_ratings WHERE ticker=?",
        (ticker.upper(),)).fetchone()
    mm = con.execute(
        "SELECT edf_implied_rating,debt_to_ebitda,interest_cov,pd_1yr FROM credit_metrics WHERE ticker=?",
        (ticker.upper(),)).fetchone()
    acts = con.execute(
        "SELECT action FROM rating_actions WHERE ticker=? ORDER BY action_date DESC LIMIT 2",
        (ticker.upper(),)).fetchall()
    con.close()
    if not rr or not mm:
        return {"error": f"No data for {ticker}", "note": _WM}

    issuer, rating, idx, outlook, watch = rr
    edf, dte, icov, pd1 = mm
    edf_idx = MOODYS_SCALE.index(edf) if edf in MOODYS_SCALE else idx

    score = 0
    signals = []
    if outlook == "Negative":
        score += 2; signals.append("Negative outlook")
    elif outlook == "Positive":
        score -= 1; signals.append("Positive outlook (mitigant)")
    if "downgrade" in (watch or "").lower():
        score += 3; signals.append("On watch for downgrade")
    if edf_idx > idx:
        score += 2; signals.append(f"Model-implied rating ({edf}) is below current ({rating})")
    elif edf_idx < idx:
        score -= 1; signals.append(f"Model-implied rating ({edf}) is above current ({rating}) (mitigant)")
    if dte and dte > 4.0:
        score += 1; signals.append(f"Elevated leverage (debt/EBITDA {dte}x)")
    if icov and icov < 3.0:
        score += 1; signals.append(f"Thin interest coverage ({icov}x)")
    recent = [a[0] for a in acts]
    if "Downgrade" in recent:
        score += 1; signals.append("Recent downgrade in the action trail")

    level = "Low" if score <= 0 else "Moderate" if score <= 3 else "Elevated"
    return {
        "ticker": ticker.upper(), "issuer": issuer, "current_rating": rating,
        "outlook": outlook, "watch_status": watch,
        "downgrade_risk": level, "risk_score": score, "signals": signals,
        "analyst_note": (f"{issuer} carries {level.lower()} downgrade risk. "
                         + ("Key drivers: " + "; ".join(signals) + "." if signals
                            else "No material deterioration signals in the synthetic data.")),
        "_watermark": _WM,
    }


if __name__ == "__main__":
    mcp.run()
