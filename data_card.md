# Data card: river ice at USGS HIVIS camera sites

## One row

One **site-day**: one USGS gage site with a HIVIS camera, on one calendar day (UTC), winter 2025–26 (Nov 1 to Apr 30).

## How many rows

| Version | Rows | Status |
|---|---|---|
| Camera table: 8 northern Wisconsin sites × 181 days | **1,448** | Have now |
| Gage table: ~704 ice-zone sites × 181 days | **~127,000** | Planned; gage columns only, no images |

Site-level reference table: 1,108 unique gage sites (from 1,356 camera records after removing duplicates).

## Columns and kinds

| Column | Kind | Notes |
|---|---|---|
| `site_no` | Categorical, key | USGS site number |
| `cam_id` | Categorical | HIVIS camera ID; some sites have more than one |
| `date` | Ordinal (time), key | Daily, UTC |
| `lat`, `lng` | Quantitative, spatial | From camera metadata |
| `state` | Categorical | |
| `frame` | Categorical (present / absent) | One frame per day near solar noon |
| `ice_score` | Quantitative, diverging around threshold | z-score of brightness, saturation, texture in the water region |
| `camera_class` | Categorical (ice / open) | Classifier output, per frame |
| `camera_in_run` | Categorical (yes / no) | Day lies in a run of 5+ ice days |
| `human_label` | Categorical (ice / partial / open / unusable) | Sparse: 400 rows, sampled evenly, one labeler |
| `discharge_cfs` | Quantitative | Daily mean |
| `discharge_qualifier` | Categorical (A / P / e) | Approved, provisional, estimated |
| `gage_ice` | Categorical (yes / no) | Derived: estimated (`e`) days in a winter block of 14+ days |
| `air_temp_c` | Quantitative, diverging around 0 °C | ERA5-Land daily mean |
| `fdd_cum` | Quantitative, cumulative | Freezing degree-days since Nov 1 |
| `jan_mean_c`, `ice_zone` | Quantitative / categorical, site-level | January 2023–26 mean; ice zone if ≤ 0 °C |

## What's missing

- **Frames:** some days have no image (Potato River: 153 of 181). After Sept 14, 2024, some cameras store daylight images only, so night conditions are never seen.
- **Unusable frames:** fog, dirty or wet lenses, snow on the lens. 10 of 400 labeled frames (2.5%), concentrated in transition seasons.
- **Human labels:** present on 400 of 1,448 site-days (28%), by design.
- **Gage ice record:** only 4 of 8 sites have any estimated-flow periods; none recorded winter water temperature.
- **Ice-zone screen:** 49 of 1,108 sites not yet screened; 3 records excluded for impossible coordinates.

## Where it came from

- **Images and camera metadata:** USGS HIVIS, via the NIMS API (course `hivis_downloader.py`), retrieved October 2026.
- **Discharge and qualifiers:** USGS NWIS daily values (parameter 00060), retrieved Oct 7, 2026. Recent values are provisional.
- **Air temperature:** ERA5-Land reanalysis via the Open-Meteo archive, at each camera's coordinates (~11 km grid).
- **River channels (for maps):** USGS NHDPlus via the NLDI service.
- **Derived columns** (`ice_score`, `camera_class`, `camera_in_run`, `gage_ice`, `fdd_cum`, `ice_zone`): my own code, CVENG 7704 project.
- **Labels:** hand-labeled by me, October 2026, in random order with the date stamp hidden.

## The one caveat I must not forget

**Missing and unusable frames are not random.** Fog, wet lenses and snow on the lens cluster in the freeze-up and break-up seasons, exactly when the timing questions are decided, and the classifier scored every one of the 10 unusable frames I labeled as ice. Any chart of ice timing that treats these frames as data, or quietly interpolates over them, will be biased toward ice at the transitions. Show them explicitly as unusable.
