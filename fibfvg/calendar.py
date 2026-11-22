"""US high-impact news days, 2024-2026 (New York dates).
FOMC = statement day (2:00 PM ET). CPI = release day (8:30 AM ET). NFP = jobs report (8:30 AM ET).
Built from the published schedules. The Oct-Nov 2025 shutdown moved some releases; dates marked
in comments. VERIFY against an economic calendar (ForexFactory, BLS, federalreserve.gov) before relying on them.
"""
import pandas as pd

FOMC = [
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]
CPI = [
    "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15", "2024-06-12", "2024-07-11", "2024-08-14",
    "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11", "2025-07-15", "2025-08-12",
    "2025-09-11", "2025-10-24",  # Oct 2025 release delayed by the shutdown; Nov 2025 release cancelled
    "2025-12-18",
    "2026-01-13", "2026-02-11", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-11", "2026-10-14", "2026-11-10",
]


def nfp_days(start="2024-01-01", end="2026-12-31"):
    """First Friday of each month (the usual NFP day). Shutdown-delayed 2025 reports are approximate."""
    out = []
    for m in pd.date_range(start, end, freq="MS"):
        d = m + pd.Timedelta(days=(4 - m.dayofweek) % 7)
        out.append(d.strftime("%Y-%m-%d"))
    return out


def news_days():
    tags = {}
    for d in FOMC:
        tags.setdefault(d, []).append("FOMC")
    for d in CPI:
        tags.setdefault(d, []).append("CPI")
    for d in nfp_days():
        tags.setdefault(d, []).append("NFP")
    return tags
