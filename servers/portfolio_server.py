"""
MFS Portfolio Analytics Desk — Cowork domain-expert plugin (MCP server).

Persona: the portfolio analytics desk supporting MFS PMs. Reasons about
holdings, active exposure vs. benchmark, attribution, guideline compliance,
and pre-trade context — the work behind a PM's decision.

DATA: 100% SYNTHETIC (data/portfolio.db). Demo only.
Run: python servers/portfolio_server.py   (stdio transport)
"""
import os
import sqlite3
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "data", "portfolio.db")

mcp = FastMCP("MFS Portfolio Analytics Desk")
_WM = "SYNTHETIC — demonstration holdings only, not actual MFS fund data."


def _con():
    return sqlite3.connect(DB)


@mcp.tool()
def list_funds() -> dict:
    """List the MFS fund lineup available to the portfolio desk, with benchmark
    and AUM. Synthetic."""
    con = _con()
    rows = con.execute("SELECT fund_id,name,benchmark,aum_usd_mm FROM funds").fetchall()
    con.close()
    return {"funds": [{"fund_id": a, "name": b, "benchmark": c, "aum_usd_mm": d}
                      for a, b, c, d in rows], "_watermark": _WM}


@mcp.tool()
def get_fund_holdings(fund_id: str, top_n: int = 15) -> dict:
    """Get the top holdings for a fund by weight, with benchmark and active weights.
    Synthetic."""
    con = _con()
    f = con.execute("SELECT name,benchmark,aum_usd_mm FROM funds WHERE fund_id=?",
                    (fund_id.upper(),)).fetchone()
    rows = con.execute(
        "SELECT ticker,name,sector,weight_pct,benchmark_wt_pct,active_wt_pct "
        "FROM holdings WHERE fund_id=? ORDER BY weight_pct DESC LIMIT ?",
        (fund_id.upper(), top_n)).fetchall()
    con.close()
    if not f:
        return {"error": f"No fund {fund_id}", "note": _WM}
    return {
        "fund_id": fund_id.upper(), "fund_name": f[0], "benchmark": f[1], "aum_usd_mm": f[2],
        "holdings": [{"ticker": a, "name": b, "sector": c, "weight_pct": d,
                      "benchmark_wt_pct": e, "active_wt_pct": f_} for a, b, c, d, e, f_ in rows],
        "_watermark": _WM,
    }


@mcp.tool()
def get_cross_fund_exposure(ticker: str) -> dict:
    """Show every MFS fund that holds a given name, with each fund's weight and
    active weight versus benchmark. The pre-trade 'where do we already own this?'
    view. Synthetic."""
    con = _con()
    rows = con.execute(
        "SELECT h.fund_id,f.name,h.weight_pct,h.benchmark_wt_pct,h.active_wt_pct,h.shares "
        "FROM holdings h JOIN funds f ON h.fund_id=f.fund_id WHERE h.ticker=? "
        "ORDER BY h.weight_pct DESC", (ticker.upper(),)).fetchall()
    con.close()
    total_shares = sum(r[5] for r in rows)
    return {
        "ticker": ticker.upper(),
        "held_by_funds": len(rows),
        "total_shares": total_shares,
        "positions": [{"fund_id": a, "fund_name": b, "weight_pct": c,
                       "benchmark_wt_pct": d, "active_wt_pct": e, "shares": f_}
                      for a, b, c, d, e, f_ in rows],
        "_watermark": _WM,
    }


@mcp.tool()
def get_attribution(fund_id: str, period: str = "2026-Q3", top_n: int = 10) -> dict:
    """Get performance attribution for a fund for a period: top contributors and
    detractors by security, split into allocation vs. selection effect (bps).
    Synthetic."""
    con = _con()
    rows = con.execute(
        "SELECT ticker,sector,allocation_bps,selection_bps,total_bps "
        "FROM attribution WHERE fund_id=? AND period=? ORDER BY total_bps DESC",
        (fund_id.upper(), period)).fetchall()
    con.close()
    if not rows:
        return {"error": f"No attribution for {fund_id} {period}", "note": _WM}
    data = [{"ticker": a, "sector": b, "allocation_bps": c, "selection_bps": d,
             "total_bps": e} for a, b, c, d, e in rows]
    contributors = data[:top_n]
    detractors = data[-top_n:][::-1]
    total = round(sum(d["total_bps"] for d in data), 1)
    return {
        "fund_id": fund_id.upper(), "period": period,
        "total_active_bps": total,
        "top_contributors": contributors,
        "top_detractors": detractors,
        "_watermark": _WM,
    }


@mcp.tool()
def get_positioning(fund_id: str) -> dict:
    """Get the positioning snapshot for a fund: active weights by sector, the
    biggest over- and under-weights versus benchmark. Synthetic."""
    con = _con()
    f = con.execute("SELECT name,benchmark FROM funds WHERE fund_id=?",
                    (fund_id.upper(),)).fetchone()
    rows = con.execute(
        "SELECT ticker,sector,weight_pct,benchmark_wt_pct,active_wt_pct "
        "FROM holdings WHERE fund_id=?", (fund_id.upper(),)).fetchall()
    con.close()
    if not f:
        return {"error": f"No fund {fund_id}", "note": _WM}
    sector_active = {}
    for a, s, w, bw, aw in rows:
        sector_active[s] = round(sector_active.get(s, 0) + aw, 2)
    names = sorted(rows, key=lambda r: r[4])
    unders = [{"ticker": r[0], "sector": r[1], "active_wt_pct": r[4]} for r in names[:5]]
    overs = [{"ticker": r[0], "sector": r[1], "active_wt_pct": r[4]} for r in names[-5:][::-1]]
    sa_sorted = sorted(sector_active.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "fund_id": fund_id.upper(), "fund_name": f[0], "benchmark": f[1],
        "sector_active_weights": [{"sector": s, "active_wt_pct": v} for s, v in sa_sorted],
        "largest_overweights": overs,
        "largest_underweights": unders,
        "_watermark": _WM,
    }


@mcp.tool()
def check_guidelines(fund_id: str) -> dict:
    """Run the investment-guideline checks for a fund and return each rule with its
    limit, current value, and pass/breach status. Surfaces active breaches first.
    Synthetic."""
    con = _con()
    rows = con.execute(
        "SELECT rule_id,description,limit_type,limit_value,current_value,status "
        "FROM guidelines WHERE fund_id=? ORDER BY (status='BREACH') DESC", (fund_id.upper(),)).fetchall()
    con.close()
    if not rows:
        return {"error": f"No guidelines for {fund_id}", "note": _WM}
    checks = [{"rule_id": a, "description": b, "limit_type": c, "limit_value": d,
               "current_value": e, "status": f_} for a, b, c, d, e, f_ in rows]
    breaches = [c for c in checks if c["status"] == "BREACH"]
    return {
        "fund_id": fund_id.upper(), "checks": checks,
        "breach_count": len(breaches),
        "summary": (f"{len(breaches)} active breach(es)." if breaches else "All guidelines within limits."),
        "_watermark": _WM,
    }


@mcp.tool()
def get_pretrade_context(ticker: str) -> dict:
    """Assemble pre-trade context for a name across the whole fund lineup: where it
    is already held and at what active weight, plus which funds' single-name limit
    the trade would push against. Synthetic."""
    con = _con()
    rows = con.execute(
        "SELECT h.fund_id,f.name,h.weight_pct,h.active_wt_pct FROM holdings h "
        "JOIN funds f ON h.fund_id=f.fund_id WHERE h.ticker=? ORDER BY h.weight_pct DESC",
        (ticker.upper(),)).fetchall()
    limits = {}
    for fid, _, _, _ in rows:
        g = con.execute("SELECT limit_value,current_value FROM guidelines "
                        "WHERE fund_id=? AND rule_id='MAX_SINGLE_NAME'", (fid,)).fetchone()
        if g:
            limits[fid] = {"limit": g[0], "current_max_name": g[1]}
    con.close()
    positions = []
    for fid, fname, w, aw in rows:
        headroom = None
        if fid in limits:
            headroom = round(limits[fid]["limit"] - w, 2)
        positions.append({"fund_id": fid, "fund_name": fname, "weight_pct": w,
                          "active_wt_pct": aw, "single_name_headroom_pct": headroom})
    return {
        "ticker": ticker.upper(),
        "currently_held_by": len(positions),
        "positions": positions,
        "note": "Headroom = single-name limit minus current weight. Negative/near-zero = limited room to add.",
        "_watermark": _WM,
    }


if __name__ == "__main__":
    mcp.run()
