#!/usr/bin/env python3
"""ratecard.py - a sponsorship rate from the views you actually get, not the ones you hope for.

    python3 ratecard.py --views 41000 18000 22500 30100 19800 26000 --cpm-low 20 --cpm-high 35
    python3 ratecard.py --views-file last10.txt --cpm-low 15 --cpm-high 30 --json

Sponsors pay for expected views, so the honest number is what a typical
video does, not the best one. This uses the MEDIAN of the last videos you
give it (10 is the convention; 5 is the floor), and the 25th-75th
percentile as the range a sponsor should expect. An average lets one hit
inflate the quote, and the sponsor finds out at the first report.

There is no default CPM. Rates vary by niche, audience geography and
placement by several times over, and a number from a blog is not yours. Use
quotes you have actually received, a rate a creator in your niche shared
with you, or what the sponsor offered. The tool refuses to guess.

The output is a starting point for a negotiation, not a quote. Usage rights,
exclusivity, whitelisting, revisions and payment terms all move it, and
none of them are in here. The /yt-sponsor skill walks through those.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from typing import Any, Dict, List, Optional

MIN_VIDEOS = 5


def percentile(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        raise ValueError("no values")
    k = (len(sorted_vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def card(views: List[float], cpm_low: float, cpm_high: float) -> Dict[str, Any]:
    if len(views) < MIN_VIDEOS:
        raise ValueError(f"need at least {MIN_VIDEOS} videos of views, got {len(views)}")
    if any(not math.isfinite(v) or v < 0 for v in views):
        raise ValueError("views must be finite and not negative")
    if not (math.isfinite(cpm_low) and math.isfinite(cpm_high)) or not 0 < cpm_low <= cpm_high:
        raise ValueError("need 0 < --cpm-low <= --cpm-high")
    s = sorted(views)
    med = statistics.median(s)
    p25, p75 = percentile(s, 0.25), percentile(s, 0.75)
    mean = statistics.mean(s)
    return {
        "videos": len(s), "median_views": round(med), "p25_views": round(p25), "p75_views": round(p75),
        "mean_views": round(mean), "mean_over_median": round(mean / med, 2) if med else None,
        "cpm_low": cpm_low, "cpm_high": cpm_high,
        "flat_fee_low": round(med / 1000 * cpm_low), "flat_fee_high": round(med / 1000 * cpm_high),
        "conservative_low": round(p25 / 1000 * cpm_low), "stretch_high": round(p75 / 1000 * cpm_high),
    }


def read_views(path: str) -> List[float]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip().replace(",", "")
            if not s or s.startswith("#"):
                continue
            out.append(float(s.split()[0]))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="A sponsorship rate card from your own median views.")
    ap.add_argument("--views", nargs="*", type=float, default=[], help="views of your recent long-form videos")
    ap.add_argument("--views-file", help="one view count per line")
    ap.add_argument("--cpm-low", type=float, required=True, help="low end of CPM, from real quotes")
    ap.add_argument("--cpm-high", type=float, required=True, help="high end of CPM, from real quotes")
    ap.add_argument("--currency", default="$", help="symbol to print (default $)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        views = list(args.views) + (read_views(args.views_file) if args.views_file else [])
        c = card(views, args.cpm_low, args.cpm_high)
    except (OSError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(c, indent=1))
        return 0
    cur = args.currency[:3]
    print(f"\n  RATE CARD  ·  last {c['videos']} long-form videos\n")
    print(f"    median views        {c['median_views']:>10,}   (what a sponsor should expect)")
    print(f"    typical range       {c['p25_views']:>10,} - {c['p75_views']:,}   (25th to 75th percentile)")
    if c["mean_over_median"] and c["mean_over_median"] > 1.3:
        print(f"    average             {c['mean_views']:>10,}   {c['mean_over_median']}x the median. One or two "
              "hits are inflating it. Do not quote off this.")
    print(f"\n    at {cur}{c['cpm_low']:g}-{cur}{c['cpm_high']:g} CPM")
    print(f"    integration, flat   {cur}{c['flat_fee_low']:,} - {cur}{c['flat_fee_high']:,}")
    print(f"    full range          {cur}{c['conservative_low']:,} (quiet video, low CPM) - "
          f"{cur}{c['stretch_high']:,} (good video, high CPM)\n")
    print("  Not a quote. Usage rights, exclusivity, whitelisting, revisions and payment terms all change it.")
    print("  Tick \"includes paid promotion\" in Studio on every sponsored upload.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
