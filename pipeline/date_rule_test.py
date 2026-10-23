#!/usr/bin/env python3
"""
date_rule_test.py - CE 7704: how much do camera ice dates depend on the date rule?

For every setting of the camera rule (minimum run length x largest gap merged),
compute freeze-up and break-up at the camera rivers and compare them with
  * the hand-label seasons (all camera rivers), and
  * the USGS gage ice seasons (rivers with a gage ice record).

The labels are the held-out test set, so this is a SENSITIVITY ANALYSIS, not
tuning: report the whole table, and justify any rule you adopt on physical or
gage grounds, not on which setting scores best against the labels.

Usage:  py pipeline/date_rule_test.py
Writes: data/date_rule_sensitivity.csv (one row per setting x river x event)
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from icedates import camera_season, gage_season, label_season

ROOT = Path(__file__).resolve().parents[1]
MIN_RUNS = (3, 5, 7)
MAX_GAPS = (0, 3, 7, 14)


def main():
    d = pd.read_csv(ROOT / "data" / "site_days.csv", dtype=str)
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d.cam_id.notna()]
    rows = []
    for site, g in d.groupby("site_no"):
        g = g.sort_values("date")
        cam = g.cam_id.iloc[0]
        lab = g[g.human_label.notna()]
        truth = dict(zip(("freeze_up", "break_up"), label_season(list(lab.date), list(lab.human_label))))
        gage = dict(zip(("freeze_up", "break_up"), gage_season(list(g.date), list(g.gage_ice.eq("yes")))))
        flags = [None if pd.isna(c) else c == "ice" for c in g.camera_class]
        if all(f is None for f in flags):
            print(f"  {cam}: no per-frame classifications - rerun batch_ice.py, then build_site_days.py")
            continue
        for mr in MIN_RUNS:
            for mg in MAX_GAPS:
                cf, cb = camera_season(list(g.date), flags, mr, mg)
                for ev, cd in (("freeze_up", cf), ("break_up", cb)):
                    rows.append({"min_run": mr, "max_gap": mg, "cam_id": cam, "event": ev,
                                 "camera": cd, "labels": truth[ev], "gage": gage[ev],
                                 "error_vs_labels": (cd - truth[ev]).days if cd and truth[ev] else None,
                                 "error_vs_gage": (cd - gage[ev]).days if cd and gage[ev] else None})
    r = pd.DataFrame(rows)
    if r.empty:
        sys.exit("nothing to evaluate")
    r.to_csv(ROOT / "data" / "date_rule_sensitivity.csv", index=False)

    def summary(col):
        x = r.dropna(subset=[col]).copy()
        x["abs"] = x[col].abs()
        return (x.groupby(["min_run", "max_gap", "event"])["abs"].agg(["median", lambda s: (s <= 7).mean()])
                 .rename(columns={"median": "median_abs_days", "<lambda_0>": "share_within_7d"})
                 .unstack("event"))

    pd.set_option("display.width", 140)
    print("\nCamera dates vs your hand-label seasons (8 rivers):")
    print(summary("error_vs_labels").round(2))
    print("\nCamera dates vs gage ice seasons (rivers with a gage ice record):")
    print(summary("error_vs_gage").round(2))
    print("\nwrote data/date_rule_sensitivity.csv")
    print("Reminder: the labels are the test set - report the table, don't pick the best row.")


if __name__ == "__main__":
    main()
