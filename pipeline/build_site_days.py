#!/usr/bin/env python3
"""
build_site_days.py - One table, one row per site-day.

One row = one USGS gage site with a HIVIS camera, on one date (UTC),
winter 2025-26 (Nov 1 to Apr 30).

  All ice-zone sites (from screened_cameras.csv):
      discharge_cfs, qualifier, gage_ice      USGS NWIS daily values (00060)
      air_temp_c, fdd_cum                     ERA5-Land via Open-Meteo
      lat, lng, state, jan_mean_c             site metadata and ice-zone screen
  The eight camera rivers, merged in:
      frame, ice_score, camera_class          batch_output/<cam>/frame_scores.csv
      camera_in_run                           batch_output/map_sites.json
      human_label                             labels.csv

Missing values are left empty on purpose. Nothing is interpolated.

Usage
    py build_site_days.py
    py build_site_days.py --limit 50        # try it on 50 sites first
Writes site_days.csv and prints a missingness summary for the data memo.

Requests are batched (USGS: 50 sites per request; Open-Meteo: 40 per request)
and every answer is cached in api_cache\\, so a rerun after a rate limit only
fetches what is missing.
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

DV = "https://waterservices.usgs.gov/nwis/dv/"
OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
HEADERS = {"Accept-Encoding": "identity", "User-Agent": "viz-design-study"}
START, END = date(2025, 11, 1), date(2026, 4, 30)
CACHE = Path("api_cache")


class FetchError(Exception):
    pass


def get_json(url, params, tries=4):
    CACHE.mkdir(exist_ok=True)
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=120)
        except requests.RequestException as e:
            last = e.__class__.__name__
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 404:
            data = {"_not_found": True}
            f.write_text(json.dumps(data))
            return data
        if r.status_code == 429 and "daily" in r.text.lower():
            raise FetchError("daily request limit reached - rerun tomorrow, cached answers are kept")
        if r.status_code == 429 or r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            time.sleep(min(int(r.headers.get("Retry-After", 0) or 0) or 30 * (attempt + 1), 180))
            continue
        if not r.ok:
            raise FetchError(f"HTTP {r.status_code}")
        data = r.json()
        f.write_text(json.dumps(data))
        return data
    raise FetchError(f"{last} after {tries} tries")


# --------------------------------------------------------------------- sites

def read_sites(path, limit):
    rows = [r for r in csv.DictReader(open(path)) if str(r.get("ice_zone")) == "True"]
    rows = [r for r in rows if r["site"].isdigit() and 8 <= len(r["site"]) <= 15]   # valid USGS site numbers
    rows.sort(key=lambda r: r["site"])
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- USGS gages

def dv_params(sites):
    return {"format": "json", "sites": ",".join(sites), "parameterCd": "00060",
            "statCd": "00003", "startDT": str(START), "endDT": str(END)}


def fetch_discharge(sites):
    """{site_no: {date: (value or None, qualifier string)}}"""
    out, rejected = {}, []
    for i in range(0, len(sites), 50):
        batch = sites[i:i + 50]
        answers = []
        try:
            answers.append(get_json(DV, dv_params(batch)))
        except FetchError as e:
            if "HTTP 400" not in str(e):
                print(f"  gage batch {i // 50 + 1} failed: {e}")
                continue
            # one bad site number makes USGS reject the whole batch: retry the sites one at a time
            print(f"  gage batch {i // 50 + 1} rejected (HTTP 400) - retrying its {len(batch)} sites one by one")
            for s in batch:
                try:
                    answers.append(get_json(DV, dv_params([s])))
                except FetchError as e2:
                    rejected.append((s, str(e2)))
                time.sleep(0.3)
        for data in answers:
            for ts in data.get("value", {}).get("timeSeries", []):
                site = ts["sourceInfo"]["siteCode"][0]["value"]
                if site in out:
                    continue                      # keep the first discharge series per site
                vals = {}
                for v in ts["values"][0]["value"]:
                    try:
                        x = float(v["value"])
                        x = None if x <= -999998 else x
                    except (TypeError, ValueError):
                        x = None
                    vals[datetime.strptime(v["dateTime"][:10], "%Y-%m-%d").date()] = (x, " ".join(v.get("qualifiers", [])))
                out[site] = vals
        print(f"  gages: {min(i + 50, len(sites))}/{len(sites)} sites requested, {len(out)} with data")
        time.sleep(0.5)
    if rejected:
        print(f"  {len(rejected)} site(s) rejected by USGS even on their own (listed in rejected_sites.txt)")
        Path("rejected_sites.txt").write_text("\n".join(f"{s}\t{e}" for s, e in rejected))
    return out


REASONS = {"Ice": "ice", "Ssn": "seasonal", "Dis": "discontinued", "Eqp": "equipment",
           "Bkw": "backwater", "Rat": "rating", "***": "unavailable", "Mnt": "maintenance", "Fld": "flood"}


def codes(q):
    return q.split() if q else []


def gage_ice_days(vals, min_block=14):
    """Ice per the gage: any day coded 'Ice' (provisional, no value published), plus days inside
    a run of estimated ('e') values at least min_block long (reviewed data, ice estimated)."""
    days = sorted(vals)
    ice = {d for d in days if "Ice" in codes(vals[d][1])}
    run = []
    for d in days + [None]:
        if d is not None and "e" in codes(vals[d][1]):
            run.append(d)
        else:
            if len(run) >= min_block:
                ice.update(run)
            run = []
    return ice


def missing_reason(value, q, has_record):
    if not has_record:
        return "no record"
    if value is not None:
        return ""
    for c in codes(q):
        if c in REASONS:
            return REASONS[c]
    return "no value"


# ------------------------------------------------------------ air temperature

def fetch_air(sites):
    """{site_no: {date: temp}}"""
    out = {}
    for i in range(0, len(sites), 40):
        batch = sites[i:i + 40]
        try:
            data = get_json(OPEN_METEO, {"latitude": ",".join(f"{float(s['lat']):.4f}" for s in batch),
                                         "longitude": ",".join(f"{float(s['lng']):.4f}" for s in batch),
                                         "daily": "temperature_2m_mean", "timezone": "UTC", "models": "era5_land",
                                         "start_date": str(START), "end_date": str(END)})
        except FetchError as e:
            print(f"  air batch {i // 40 + 1} failed: {e}")
            if "daily" in str(e):
                break
            continue
        data = data if isinstance(data, list) else [data]
        for s, d in zip(batch, data):
            dd = (d or {}).get("daily", {})
            out[s["site"]] = {datetime.strptime(t, "%Y-%m-%d").date(): v
                              for t, v in zip(dd.get("time", []), dd.get("temperature_2m_mean", [])) if v is not None}
        print(f"  air temperature: {min(i + 40, len(sites))}/{len(sites)} sites")
        time.sleep(1.5)
    return out


# ------------------------------------------------------------- camera merge

def camera_columns(root):
    """{(site_no, date): {...}} for the camera rivers, if their files exist."""
    out = {}
    sites_json = Path(root) / "map_sites.json"
    if not sites_json.exists():
        return out
    labels = defaultdict(dict)
    if Path("labels.csv").exists():
        for r in csv.DictReader(open("labels.csv")):
            labels[r["cam_id"]][r["date"]] = r["label"]
    for s in json.loads(sites_json.read_text())["sites"]:
        cam, site = s["cam_id"], s["nwis_id"]
        runs = s["camera_runs"]
        frames = {}
        fs = Path(root) / cam / "frame_scores.csv"
        if fs.exists():
            frames = {r["date"]: r for r in csv.DictReader(open(fs))}
        d = START
        while d <= END:
            k = d.isoformat()
            fr = frames.get(k)
            lab = labels[cam].get(k, "")
            out[(site, d)] = {
                "cam_id": cam,
                "frame": "unusable" if lab == "unusable" else ("present" if fr else ("absent" if frames else "")),
                "ice_score": fr["score"] if fr else "",
                "camera_class": fr["classified"] if fr else "",
                "camera_in_run": "yes" if any(a <= k <= b for a, b in runs) else ("no" if fr else ""),
                "human_label": lab,
            }
            d += timedelta(days=1)
    return out


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default="screened_cameras.csv")
    ap.add_argument("--root", default="batch_output")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="site_days.csv")
    args = ap.parse_args()
    if not Path(args.sites).exists():
        sys.exit(f"{args.sites} not found - run screen_cameras.py / topup_screen.py first")

    sites = read_sites(args.sites, args.limit)
    print(f"{len(sites)} ice-zone sites")
    q = fetch_discharge([s["site"] for s in sites])
    air = fetch_air(sites)
    cams = camera_columns(args.root)

    cols = ["site_no", "date", "state", "lat", "lng", "jan_mean_c", "discharge_cfs", "qualifier", "missing_reason", "gage_ice",
            "air_temp_c", "fdd_cum", "cam_id", "frame", "ice_score", "camera_class", "camera_in_run", "human_label"]
    n = 0
    filled = defaultdict(int)
    cam_sites = set()
    reasons = defaultdict(int)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for s in sites:
            site = s["site"]
            vals = q.get(site, {})
            ice = gage_ice_days(vals) if vals else set()
            temps = air.get(site, {})
            fdd = 0.0
            d = START
            while d <= END:
                x, qual = vals.get(d, (None, ""))
                t = temps.get(d)
                if t is not None:
                    fdd += max(0.0, -t)
                row = {"site_no": site, "date": d.isoformat(), "state": s.get("state", ""),
                       "lat": s["lat"], "lng": s["lng"], "jan_mean_c": s.get("jan_mean_c", ""),
                       "discharge_cfs": "" if x is None else x, "qualifier": qual,
                       "missing_reason": missing_reason(x, qual, bool(vals)),
                       "gage_ice": ("yes" if d in ice else "no") if vals else "",
                       "air_temp_c": "" if t is None else round(t, 1),
                       "fdd_cum": round(fdd, 1) if temps else ""}
                if row["missing_reason"]:
                    reasons[row["missing_reason"]] += 1
                if (site, d) in cams:
                    row.update(cams[(site, d)])
                    cam_sites.add(site)
                w.writerow(row)
                n += 1
                for c in cols:
                    if row.get(c, "") != "":
                        filled[c] += 1
                d += timedelta(days=1)

    print(f"\nwrote {args.out}: {n:,} rows ({len(sites)} sites x {(END - START).days + 1} days)")
    print("\nMissingness (share of rows with a value) - for the data memo:")
    for c in cols:
        print(f"  {c:15s} {filled[c] / n:6.1%}")
    print("\nWhy discharge is missing (rows):")
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {k:13s} {v:7,d}")
    print(f"\n  sites with any discharge record: {len(q)} of {len(sites)}")
    print(f"  sites with air temperature:      {len(air)} of {len(sites)}")
    print(f"  sites with camera columns:       {len(cam_sites)}")
    if any(not (Path(args.root) / s["cam_id"] / "frame_scores.csv").exists()
           for s in json.loads((Path(args.root) / "map_sites.json").read_text())["sites"]) if (Path(args.root) / "map_sites.json").exists() else False:
        print("  note: some cameras have no frame_scores.csv - rerun batch_ice.py so frame and ice_score are filled")


if __name__ == "__main__":
    main()
