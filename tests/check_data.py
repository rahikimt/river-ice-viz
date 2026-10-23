#!/usr/bin/env python3
"""
check_data.py - Assert what the data memo claims, so a pipeline change can't
silently break it. Run after every rebuild:  py tests/check_data.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "data"
fails = []


def check(ok, msg):
    print(("  ok    " if ok else "  FAIL  ") + msg)
    if not ok:
        fails.append(msg)


d = pd.read_csv(ROOT / "site_days.csv", dtype=str)
s = pd.read_csv(ROOT / "sites.csv", dtype=str)
e = pd.read_csv(ROOT / "events.csv", dtype=str)
n_sites, n_days = d.site_no.nunique(), d.date.nunique()

print("site_days.csv")
check(len(d) == n_sites * n_days, f"one row per site-day: {len(d):,} = {n_sites} sites x {n_days} days")
check(not d.duplicated(["site_no", "date"]).any(), "no duplicate (site_no, date) keys")
check(d.date.min() == "2025-11-01" and d.date.max() == "2026-04-30", f"season {d.date.min()} to {d.date.max()}")
check(d.site_no.str.fullmatch(r"\d{8,15}").all(), "every site_no is a valid USGS number (8-15 digits)")
check(len(d) >= 10_000, "at least 10,000 records (petition requirement)")
no_rec = d.missing_reason.eq("no record")
check(d.loc[no_rec, "gage_ice"].isna().all(), "no gage-ice value invented at sites without a record")
check(d.loc[d.discharge_cfs.notna(), "missing_reason"].isna().all(), "missing_reason only where discharge is missing")
check(d.air_temp_c.notna().mean() > 0.99, f"air temperature present on {d.air_temp_c.notna().mean():.1%} of rows")
labs = d.human_label.dropna()
check(set(labs) <= {"ice", "partial", "open", "unusable"}, "labels use only ice / partial / open / unusable")
check(d[d.cam_id.notna()].site_no.nunique() == 8, "camera columns at exactly the 8 camera rivers")

print("sites.csv / events.csv")
check(len(s) == n_sites and s.site_no.is_unique, f"one row per site ({len(s)})")
check(set(e.source) <= {"gage", "camera", "labels"} and set(e.event) <= {"freeze_up", "break_up"},
      "events use only known sources and event names")
pairs = e.groupby(["site_no", "source"]).event.apply(lambda x: sorted(x) == ["break_up", "freeze_up"])
check(pairs.all(), "every site-source has both a freeze-up and a break-up")
w = e.pivot_table(index=["site_no", "source"], columns="event", values="date", aggfunc="first")
check((w.freeze_up <= w.break_up).all(), "freeze-up never after break-up")

print(f"\n{len(fails)} failure(s)" if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
