#!/usr/bin/env python3
"""
make_derived.py - Build the tables every view and analysis reads, from site_days.csv.

  data/sites.csv    one row per site: location, gage coverage, why data are missing,
                    camera and label coverage, gage ice season
  data/events.csv   one row per site x event x source: freeze-up and break-up dates
                    from the gage, the camera and the hand labels
  data/daily.csv    one row per site-day, only the columns that change day to day
                    (site attributes live in sites.csv)

Everything is copied to docs/data/ for the web app. Nothing here is a design
decision; the views come from the sketches.

Usage:  py pipeline/make_derived.py
        py pipeline/make_derived.py --min-run 5 --max-gap 14     # camera date rule
"""

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from icedates import camera_season, gage_season, label_season

ROOT = Path(__file__).resolve().parents[1]
DAILY_COLS = ["site_no", "date", "discharge_cfs", "missing_reason", "gage_ice", "air_temp_c", "fdd_cum",
              "frame", "ice_score", "camera_class", "camera_in_run", "human_label"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "data" / "site_days.csv"))
    ap.add_argument("--min-run", type=int, default=5)
    ap.add_argument("--max-gap", type=int, default=3)
    args = ap.parse_args()

    d = pd.read_csv(args.input, dtype=str)
    d["date"] = pd.to_datetime(d["date"]).dt.date
    print(f"read {len(d):,} site-days for {d.site_no.nunique()} sites")

    # ------------------------------------------------------------------ sites
    rows, events = [], []
    for site, g in d.groupby("site_no", sort=True):
        g = g.sort_values("date")
        first = g.iloc[0]
        has_record = g.gage_ice.notna().any()
        reasons = g.missing_reason.value_counts()
        ice_days = g.gage_ice.eq("yes")
        gf, gb = gage_season(list(g.date), list(ice_days))
        cam = g.cam_id.dropna()
        rows.append({
            "site_no": site, "state": first.state, "lat": first.lat, "lng": first.lng,
            "jan_mean_c": first.jan_mean_c,
            "has_discharge_record": "yes" if has_record else "no",
            "days_with_discharge": int(g.discharge_cfs.notna().sum()),
            "gage_ice_days": int(ice_days.sum()),
            "gage_ice_first": gf or "", "gage_ice_last": gb or "",
            "missing_ice": int(reasons.get("ice", 0)),
            "missing_no_value": int(reasons.get("no value", 0)),
            "missing_other": int(reasons.drop(["ice", "no value", "no record"], errors="ignore").sum()),
            "cam_id": cam.iloc[0] if len(cam) else "",
            "frames": int(g.frame.eq("present").sum() + g.frame.eq("unusable").sum()),
            "labels": int(g.human_label.notna().sum()),
            "peak_fdd": round(pd.to_numeric(g.fdd_cum).max(), 1) if g.fdd_cum.notna().any() else "",
        })
        if gf:
            events += [{"site_no": site, "event": "freeze_up", "source": "gage", "date": gf},
                       {"site_no": site, "event": "break_up", "source": "gage", "date": gb}]
        if len(cam):
            flags = [None if c is None or pd.isna(c) else c == "ice" for c in g.camera_class]
            cf, cb = camera_season(list(g.date), flags, args.min_run, args.max_gap)
            if cf:
                events += [{"site_no": site, "event": "freeze_up", "source": "camera", "date": cf},
                           {"site_no": site, "event": "break_up", "source": "camera", "date": cb}]
            lab = g[g.human_label.notna()]
            lf, lb = label_season(list(lab.date), list(lab.human_label))
            if lf:
                events += [{"site_no": site, "event": "freeze_up", "source": "labels", "date": lf},
                           {"site_no": site, "event": "break_up", "source": "labels", "date": lb}]

    sites = pd.DataFrame(rows)
    ev = pd.DataFrame(events, columns=["site_no", "event", "source", "date"])
    out = ROOT / "data"
    sites.to_csv(out / "sites.csv", index=False)
    ev.to_csv(out / "events.csv", index=False)
    d[DAILY_COLS].to_csv(out / "daily.csv", index=False)

    docs = ROOT / "docs" / "data"
    docs.mkdir(parents=True, exist_ok=True)
    for f in ("sites.csv", "events.csv", "daily.csv"):
        shutil.copy(out / f, docs / f)

    print(f"wrote data/sites.csv ({len(sites)} sites), data/events.csv ({len(ev)} events), "
          f"data/daily.csv ({len(d):,} rows); copied to docs/data/")
    print(f"camera date rule: runs of {args.min_run}+ ice days, gaps up to {args.max_gap} days merged")
    print(f"sites with a gage ice season: {(sites.gage_ice_days > 0).sum()}, "
          f"with camera dates: {ev[ev.source == 'camera'].site_no.nunique()}, "
          f"with label dates: {ev[ev.source == 'labels'].site_no.nunique()}")


if __name__ == "__main__":
    main()
