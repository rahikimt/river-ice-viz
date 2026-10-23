"""
icedates.py - Turn daily ice observations into freeze-up and break-up dates.

Shared by both projects: CE 7704 computes and evaluates the dates, CS 8630 shows them.
Three sources, three rules, each documented so the choice can be defended:

  camera  daily classifier verdicts (one per available frame). Runs of at least
          `min_run` ice observations, gaps of at most `max_gap` days merged, and the
          longest merged block is the ice season. Missing frames neither extend nor
          break a run.
  labels  hand labels, about every 3.7 days. Ice or partial ice counts as ice; a
          season runs from the first to the last pair of consecutive ice labels.
  gage    USGS ice-affected days. Season = first to last ice day.
"""


def _runs(dates, flags):
    """Runs of consecutive True observations -> [(start, end), ...]. None = no observation."""
    obs = [(d, f) for d, f in zip(dates, flags) if f is not None]
    out, start, prev = [], None, None
    for d, f in obs + [(None, False)]:
        if f and start is None:
            start = d
        if not f and start is not None:
            out.append((start, prev))
            start = None
        prev = d
    return out, obs


def camera_season(dates, flags, min_run=5, max_gap=3):
    """(freeze_up, break_up) or (None, None). `flags`: True ice, False open, None missing."""
    runs, obs = _runs(dates, flags)
    idx = {d: i for i, (d, _) in enumerate(obs)}
    runs = [(a, b) for a, b in runs if idx[b] - idx[a] + 1 >= min_run]
    merged = []
    for a, b in runs:
        if merged and (a - merged[-1][1]).days - 1 <= max_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if not merged:
        return None, None
    return max(merged, key=lambda ab: (ab[1] - ab[0]).days)


def label_season(dates, labels):
    """Season from sparse hand labels ('ice', 'partial', 'open', 'unusable')."""
    flags = [None if l == "unusable" else l in ("ice", "partial") for l in labels]
    runs, obs = _runs(dates, flags)
    idx = {d: i for i, (d, _) in enumerate(obs)}
    runs = [(a, b) for a, b in runs if idx[b] - idx[a] >= 1]      # at least two consecutive labels
    if not runs:
        return None, None
    return runs[0][0], runs[-1][1]


def gage_season(dates, ice):
    """First and last ice-affected day."""
    days = [d for d, i in zip(dates, ice) if i]
    return (min(days), max(days)) if days else (None, None)
