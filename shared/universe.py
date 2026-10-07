"""
Shared demo universe for the MFS Cowork demo.

~50 real large/mid-cap tickers across GICS sectors. FinnHub returns REAL data
for the equity-research server; the credit and portfolio servers wrap these
SAME tickers with SIMULATED data so the end-to-end story stays coherent.

All credit ratings, fund holdings, and portfolio analytics derived from this
file are SYNTHETIC and for demonstration only.
"""

# ticker: (company name, GICS sector, approx mkt-cap tier)
UNIVERSE = {
    # Information Technology
    "AAPL":  ("Apple Inc.",                 "Information Technology", "mega"),
    "MSFT":  ("Microsoft Corporation",      "Information Technology", "mega"),
    "NVDA":  ("NVIDIA Corporation",         "Information Technology", "mega"),
    "AVGO":  ("Broadcom Inc.",              "Information Technology", "large"),
    "CRM":   ("Salesforce, Inc.",           "Information Technology", "large"),
    "ORCL":  ("Oracle Corporation",         "Information Technology", "large"),
    "AMD":   ("Advanced Micro Devices",     "Information Technology", "large"),
    # Communication Services
    "GOOGL": ("Alphabet Inc.",              "Communication Services", "mega"),
    "META":  ("Meta Platforms, Inc.",       "Communication Services", "mega"),
    "NFLX":  ("Netflix, Inc.",              "Communication Services", "large"),
    "DIS":   ("The Walt Disney Company",    "Communication Services", "large"),
    "TMUS":  ("T-Mobile US, Inc.",          "Communication Services", "large"),
    # Consumer Discretionary
    "AMZN":  ("Amazon.com, Inc.",           "Consumer Discretionary", "mega"),
    "TSLA":  ("Tesla, Inc.",                "Consumer Discretionary", "mega"),
    "HD":    ("The Home Depot, Inc.",       "Consumer Discretionary", "large"),
    "NKE":   ("NIKE, Inc.",                 "Consumer Discretionary", "large"),
    "MCD":   ("McDonald's Corporation",     "Consumer Discretionary", "large"),
    "SBUX":  ("Starbucks Corporation",      "Consumer Discretionary", "large"),
    # Consumer Staples
    "PG":    ("Procter & Gamble Company",   "Consumer Staples",       "large"),
    "KO":    ("The Coca-Cola Company",      "Consumer Staples",       "large"),
    "PEP":   ("PepsiCo, Inc.",              "Consumer Staples",       "large"),
    "COST":  ("Costco Wholesale Corp.",     "Consumer Staples",       "large"),
    "WMT":   ("Walmart Inc.",               "Consumer Staples",       "large"),
    # Health Care
    "UNH":   ("UnitedHealth Group Inc.",    "Health Care",            "large"),
    "JNJ":   ("Johnson & Johnson",          "Health Care",            "large"),
    "LLY":   ("Eli Lilly and Company",      "Health Care",            "mega"),
    "PFE":   ("Pfizer Inc.",                "Health Care",            "large"),
    "ABBV":  ("AbbVie Inc.",                "Health Care",            "large"),
    "MRK":   ("Merck & Co., Inc.",          "Health Care",            "large"),
    # Financials
    "JPM":   ("JPMorgan Chase & Co.",       "Financials",             "large"),
    "BAC":   ("Bank of America Corp.",      "Financials",             "large"),
    "WFC":   ("Wells Fargo & Company",      "Financials",             "large"),
    "GS":    ("The Goldman Sachs Group",    "Financials",             "large"),
    "MS":    ("Morgan Stanley",             "Financials",             "large"),
    "BLK":   ("BlackRock, Inc.",            "Financials",             "large"),
    # Industrials
    "CAT":   ("Caterpillar Inc.",           "Industrials",            "large"),
    "BA":    ("The Boeing Company",         "Industrials",            "large"),
    "HON":   ("Honeywell International",     "Industrials",            "large"),
    "UPS":   ("United Parcel Service",      "Industrials",            "large"),
    "GE":    ("GE Aerospace",               "Industrials",            "large"),
    # Energy
    "XOM":   ("Exxon Mobil Corporation",    "Energy",                 "large"),
    "CVX":   ("Chevron Corporation",        "Energy",                 "large"),
    "COP":   ("ConocoPhillips",             "Energy",                 "large"),
    # Materials
    "LIN":   ("Linde plc",                  "Materials",              "large"),
    "SHW":   ("The Sherwin-Williams Co.",   "Materials",              "large"),
    "FCX":   ("Freeport-McMoRan Inc.",      "Materials",              "large"),
    # Utilities
    "NEE":   ("NextEra Energy, Inc.",       "Utilities",              "large"),
    "DUK":   ("Duke Energy Corporation",    "Utilities",              "large"),
    "SO":    ("The Southern Company",       "Utilities",              "large"),
    # Real Estate
    "PLD":   ("Prologis, Inc.",             "Real Estate",            "large"),
    "AMT":   ("American Tower Corp.",       "Real Estate",            "large"),
}

TICKERS = list(UNIVERSE.keys())

# MFS-style fund lineup (SYNTHETIC) that the portfolio server reports on.
FUNDS = {
    "MGEX": ("MFS Growth Equity Fund",        "Russell 1000 Growth",
             ["Information Technology", "Communication Services", "Consumer Discretionary", "Health Care"]),
    "MVAL": ("MFS Value Fund",                "Russell 1000 Value",
             ["Financials", "Health Care", "Consumer Staples", "Industrials", "Energy"]),
    "MCOR": ("MFS Core Equity Fund",          "S&P 500",
             None),  # broad
    "MGLB": ("MFS Global Equity Fund",        "MSCI World",
             None),  # broad
    "MDIV": ("MFS Dividend Income Fund",      "S&P 500 High Dividend",
             ["Consumer Staples", "Utilities", "Financials", "Health Care", "Real Estate", "Energy"]),
}

SECTORS = sorted({v[1] for v in UNIVERSE.values()})

WATERMARK = "SYNTHETIC DATA — generated for Microsoft Copilot Cowork demonstration only. Not MFS, Moody's, FactSet, or any provider data."

if __name__ == "__main__":
    print(f"{len(TICKERS)} tickers across {len(SECTORS)} GICS sectors")
    print(f"{len(FUNDS)} synthetic MFS funds")
    for s in SECTORS:
        names = [t for t, v in UNIVERSE.items() if v[1] == s]
        print(f"  {s:28s} {', '.join(names)}")
