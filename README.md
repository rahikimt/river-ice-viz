# River ice at USGS HIVIS camera sites

Design study (CS 8630) and ice-dating analysis (CE 7704), sharing one data pipeline.
Winter 2025–26, one row per site-day.

## Layout

| Folder | Contents |
|---|---|
| `pipeline/` | Data building (`build_site_days.py`), ice-dating rules (`icedates.py`), derived tables (`make_derived.py`), CE 7704 date-rule test (`date_rule_test.py`) |
| `data/` | `site_days.csv` (one row per site-day), `sites.csv`, `events.csv`, `daily.csv`, `labels.csv` |
| `tests/` | `check_data.py`: asserts the claims in the data memo |
| `docs/` | Web prototype (GitHub Pages serves this folder) |
| `sketches/` | Hand-drawn design sketches (Milestone 2, no AI) |

## Rebuild

`build_site_days.py` needs the camera outputs (`screened_cameras.csv`, `batch_output/`, `labels.csv`), so run it from the CE 7704 project folder and point its output here:

```
py build_site_days.py --out <path-to-this-repo>\data\site_days.csv
```

Then, from this repo:

```
py pipeline/make_derived.py
py tests/check_data.py
py pipeline/date_rule_test.py       # CE 7704
```

View the prototype locally: `py -m http.server` in `docs/`, then open http://localhost:8000.

## Sources

USGS HIVIS (NIMS API); USGS NWIS daily discharge, retrieved Oct 7, 2026 (provisional);
ERA5-Land via the Open-Meteo archive; USGS NHDPlus via NLDI. See `data_card.md`.

## AI use

Documented in `AI-LOG.md`. The hand sketches in `sketches/` were made without AI.
