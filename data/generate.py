"""
Synthetic data generator for the MFS Cowork demo.

Builds two SQLite databases over the SHARED real-ticker universe:
  data/credit.db     -- Moody's-style issuer ratings, rating actions, credit metrics
  data/portfolio.db  -- MFS-style fund holdings, benchmark weights, guidelines

ALL DATA IS SYNTHETIC. Deterministic (seeded) so the demo is reproducible.
Ratings/holdings are internally consistent with sector and cap tier so the
numbers "feel" right next to the REAL FinnHub fundamentals.
"""
import os
import sqlite3
import random
import datetime as dt
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from universe import UNIVERSE, TICKERS, FUNDS, WATERMARK  # noqa: E402

HERE = os.path.dirname(__file__)
CREDIT_DB = os.path.join(HERE, "credit.db")
PORT_DB = os.path.join(HERE, "portfolio.db")

SEED = 1924  # the year MFS was founded
random.seed(SEED)

# Moody's long-term scale (best -> worst)
MOODYS_SCALE = [
    "Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3",
    "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3",
    "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C",
]
IG_CUTOFF = MOODYS_SCALE.index("Baa3")  # <= this index is investment grade
OUTLOOKS = ["Stable", "Positive", "Negative", "Developing"]

# Rough sector credit bias: where on the scale an issuer tends to sit
SECTOR_BIAS = {
    "Information Technology": 3,   # A-ish
    "Communication Services": 5,
    "Consumer Discretionary": 6,
    "Consumer Staples": 2,         # strong
    "Health Care": 3,
    "Financials": 5,
    "Industrials": 5,
    "Energy": 7,                   # more cyclical
    "Materials": 8,
    "Utilities": 4,                # stable, levered
    "Real Estate": 7,
}
CAP_ADJ = {"mega": -2, "large": 0, "mid": 2}


def rating_for(ticker):
    name, sector, cap = UNIVERSE[ticker]
    base = SECTOR_BIAS.get(sector, 6) + CAP_ADJ.get(cap, 0)
    jitter = random.randint(-1, 2)
    idx = max(0, min(len(MOODYS_SCALE) - 1, base + jitter))
    return idx


def build_credit():
    if os.path.exists(CREDIT_DB):
        os.remove(CREDIT_DB)
    con = sqlite3.connect(CREDIT_DB)
    c = con.cursor()
    c.executescript("""
    CREATE TABLE meta (key TEXT, value TEXT);
    CREATE TABLE issuer_ratings (
        ticker TEXT PRIMARY KEY, issuer TEXT, sector TEXT,
        lt_rating TEXT, rating_idx INTEGER, grade TEXT,
        outlook TEXT, watch TEXT, last_action_date TEXT
    );
    CREATE TABLE rating_actions (
        ticker TEXT, action_date TEXT, action TEXT,
        from_rating TEXT, to_rating TEXT, rationale TEXT
    );
    CREATE TABLE credit_metrics (
        ticker TEXT PRIMARY KEY,
        pd_1yr REAL, pd_5yr REAL, lgd REAL, recovery REAL,
        debt_to_ebitda REAL, interest_cov REAL, ffo_to_debt REAL,
        edf_implied_rating TEXT
    );
    """)
    c.execute("INSERT INTO meta VALUES (?,?)", ("watermark", WATERMARK))
    c.execute("INSERT INTO meta VALUES (?,?)", ("generated", dt.datetime.now().isoformat()))
    c.execute("INSERT INTO meta VALUES (?,?)", ("seed", str(SEED)))

    today = dt.date.today()
    for t in TICKERS:
        name, sector, cap = UNIVERSE[t]
        idx = rating_for(t)
        rating = MOODYS_SCALE[idx]
        grade = "Investment Grade" if idx <= IG_CUTOFF else "High Yield"
        outlook = random.choices(OUTLOOKS, weights=[60, 15, 20, 5])[0]
        watch = "None"
        if random.random() < 0.12:
            watch = random.choice(["On watch — possible downgrade", "On watch — possible upgrade"])

        # rating action history (2-4 actions over ~5 yrs)
        n_actions = random.randint(2, 4)
        cur_idx = idx + random.randint(0, 3)  # started a bit different
        cur_idx = max(0, min(len(MOODYS_SCALE) - 1, cur_idx))
        action_dates = sorted(
            today - dt.timedelta(days=random.randint(90, 1825)) for _ in range(n_actions)
        )
        last_date = None
        prev_idx = cur_idx
        for i, d in enumerate(action_dates):
            if i == len(action_dates) - 1:
                to_idx = idx  # end at current
            else:
                to_idx = max(0, min(len(MOODYS_SCALE) - 1, prev_idx + random.choice([-1, 0, 1])))
            if to_idx < prev_idx:
                action = "Upgrade"
            elif to_idx > prev_idx:
                action = "Downgrade"
            else:
                action = "Affirmed"
            rationale = {
                "Upgrade": "Improved leverage profile and sustained free-cash-flow generation.",
                "Downgrade": "Rising leverage and margin pressure in a softening demand environment.",
                "Affirmed": "Credit profile consistent with expectations; stable operating performance.",
            }[action]
            c.execute("INSERT INTO rating_actions VALUES (?,?,?,?,?,?)",
                      (t, d.isoformat(), action, MOODYS_SCALE[prev_idx],
                       MOODYS_SCALE[to_idx], rationale))
            prev_idx = to_idx
            last_date = d

        # credit metrics consistent with rating
        sev = idx / len(MOODYS_SCALE)
        pd1 = round(0.02 + sev * 4.5 + random.uniform(-0.01, 0.05), 3)
        pd5 = round(pd1 * (3.2 + random.uniform(-0.3, 0.6)), 3)
        lgd = round(0.35 + sev * 0.25 + random.uniform(-0.05, 0.05), 2)
        recovery = round(1 - lgd, 2)
        dte = round(1.2 + sev * 5.5 + random.uniform(-0.3, 0.6), 2)
        icov = round(max(0.8, 14 - sev * 16 + random.uniform(-1, 1)), 2)
        ffo = round(max(0.03, 0.65 - sev * 0.55 + random.uniform(-0.03, 0.03)), 2)
        edf_idx = max(0, min(len(MOODYS_SCALE) - 1, idx + random.choice([-1, 0, 0, 1])))

        c.execute("INSERT INTO credit_metrics VALUES (?,?,?,?,?,?,?,?,?)",
                  (t, pd1, pd5, lgd, recovery, dte, icov, ffo, MOODYS_SCALE[edf_idx]))
        c.execute("INSERT INTO issuer_ratings VALUES (?,?,?,?,?,?,?,?,?)",
                  (t, name, sector, rating, idx, grade, outlook, watch,
                   last_date.isoformat() if last_date else today.isoformat()))

    con.commit()
    n = c.execute("SELECT COUNT(*) FROM issuer_ratings").fetchone()[0]
    na = c.execute("SELECT COUNT(*) FROM rating_actions").fetchone()[0]
    con.close()
    print(f"credit.db: {n} issuers, {na} rating actions")


def build_portfolio():
    if os.path.exists(PORT_DB):
        os.remove(PORT_DB)
    con = sqlite3.connect(PORT_DB)
    c = con.cursor()
    c.executescript("""
    CREATE TABLE meta (key TEXT, value TEXT);
    CREATE TABLE funds (
        fund_id TEXT PRIMARY KEY, name TEXT, benchmark TEXT, aum_usd_mm REAL
    );
    CREATE TABLE holdings (
        fund_id TEXT, ticker TEXT, name TEXT, sector TEXT,
        weight_pct REAL, benchmark_wt_pct REAL, active_wt_pct REAL,
        shares INTEGER, cost_basis REAL
    );
    CREATE TABLE attribution (
        fund_id TEXT, period TEXT, ticker TEXT, sector TEXT,
        allocation_bps REAL, selection_bps REAL, total_bps REAL
    );
    CREATE TABLE guidelines (
        fund_id TEXT, rule_id TEXT, description TEXT,
        limit_type TEXT, limit_value REAL, current_value REAL, status TEXT
    );
    """)
    c.execute("INSERT INTO meta VALUES (?,?)", ("watermark", WATERMARK))
    c.execute("INSERT INTO meta VALUES (?,?)", ("generated", dt.datetime.now().isoformat()))

    period = "2026-Q3"
    for fid, (fname, bench, sector_focus) in FUNDS.items():
        aum = round(random.uniform(3500, 42000), 1)
        c.execute("INSERT INTO funds VALUES (?,?,?,?)", (fid, fname, bench, aum))

        # choose holdings: sector-focused funds tilt to their sectors
        if sector_focus:
            pool = [t for t in TICKERS if UNIVERSE[t][1] in sector_focus]
            extra = [t for t in TICKERS if t not in pool]
            random.shuffle(extra)
            pool = pool + extra[:8]
        else:
            pool = list(TICKERS)
        random.shuffle(pool)
        n_hold = random.randint(28, 40)
        picks = pool[:n_hold]

        # random active weights, normalized
        raw = [random.uniform(0.5, 5.0) for _ in picks]
        tot = sum(raw)
        weights = [round(w / tot * 100, 2) for w in raw]
        for t, w in zip(picks, weights):
            name, sector, cap = UNIVERSE[t]
            bench_wt = round(max(0.0, w + random.uniform(-2.2, 1.5)), 2)
            active = round(w - bench_wt, 2)
            shares = int(random.uniform(50_000, 3_000_000))
            cost = round(random.uniform(40, 520), 2)
            c.execute("INSERT INTO holdings VALUES (?,?,?,?,?,?,?,?,?)",
                      (fid, t, name, sector, w, bench_wt, active, shares, cost))

            # attribution for the quarter
            alloc = round(random.uniform(-25, 25), 1)
            sel = round(random.uniform(-45, 55), 1)
            c.execute("INSERT INTO attribution VALUES (?,?,?,?,?,?,?)",
                      (fid, period, t, sector, alloc, sel, round(alloc + sel, 1)))

        # guidelines (a few per fund, mostly passing, occasional breach)
        rules = [
            ("MAX_SINGLE_NAME", "No single position above 6% of NAV", "max", 6.0),
            ("MAX_SECTOR", "No single GICS sector above 35% of NAV", "max", 35.0),
            ("MIN_HOLDINGS", "Hold at least 25 names", "min", 25.0),
            ("MAX_CASH", "Cash no greater than 5% of NAV", "max", 5.0),
            ("MAX_NONBENCH", "Off-benchmark names no more than 20% of NAV", "max", 20.0),
        ]
        top_wt = max(weights)
        # sector concentration
        sector_tot = {}
        for t, w in zip(picks, weights):
            s = UNIVERSE[t][1]
            sector_tot[s] = sector_tot.get(s, 0) + w
        max_sector = max(sector_tot.values())
        current_map = {
            "MAX_SINGLE_NAME": round(top_wt, 2),
            "MAX_SECTOR": round(max_sector, 2),
            "MIN_HOLDINGS": float(len(picks)),
            "MAX_CASH": round(random.uniform(0.5, 4.5), 2),
            "MAX_NONBENCH": round(random.uniform(8, 22), 2),
        }
        for rid, desc, ltype, lval in rules:
            cur = current_map[rid]
            if ltype == "max":
                status = "BREACH" if cur > lval else "OK"
            else:
                status = "BREACH" if cur < lval else "OK"
            c.execute("INSERT INTO guidelines VALUES (?,?,?,?,?,?,?)",
                      (fid, rid, desc, ltype, lval, cur, status))

    con.commit()
    nf = c.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
    nh = c.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
    nb = c.execute("SELECT COUNT(*) FROM guidelines WHERE status='BREACH'").fetchone()[0]
    con.close()
    print(f"portfolio.db: {nf} funds, {nh} holdings, {nb} guideline breaches")


if __name__ == "__main__":
    build_credit()
    build_portfolio()
    print("Done. All data SYNTHETIC — demo only.")
