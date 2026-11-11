#!/usr/bin/env python3
"""channel.py - read a YouTube Studio content export and name the ONE fix.

    python3 channel.py "Table data.csv"
    python3 channel.py "Table data.csv" --last 20 --json
    python3 channel.py "Table data.csv" --include-shorts

Get the file: Studio -> Analytics -> Advanced mode -> Content, pick the date
range, add the Impressions, Impressions click-through rate, Average view
duration and Average percentage viewed columns if they are not there, then
the download icon -> "Comma-separated values". Columns are matched loosely,
and the "Total" row is skipped.

Every video is judged against THIS channel, not against a benchmark from a
blog. That is the whole method:

  multiple    views / the channel's median views. Above 2x is a signal.
  CTR         impressions click-through rate, against the channel's median
  APV         average percentage viewed, against the channel's median

Then each video lands in one quadrant, and each quadrant has a different fix:

  high CTR, high APV   WORKING     make the next one like this
  high CTR, low APV    RETENTION   the packaging promised more than the video
                                   delivered, or the opening leaks. /yt-retention
  low CTR, high APV    PACKAGING   a good video nobody clicked. /yt-package
  low CTR, low APV     TOPIC       the idea itself. /yt-viral before /yt-script

The medians come from every long-form video in the export; the fix comes
from how the most recent ones (--last, default 10) compare to them. A median
split puts about half of all videos on each side by definition, so the
question it answers is "how are my recent videos drifting against my own
history". Export at least 30 videos so there is a history to drift from.

The ONE fix is the problem quadrant that holds the most of the recent
videos. Shorts (180 seconds or under) are left out by default, because their
views and CTR live on a different scale and would bend every median.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "..", "yt-script", "hooks.json"), encoding="utf-8") as _fh:
    FORMULAS = json.load(_fh)["hooks"]

FIELDS: Dict[str, List[str]] = {
    "id":          ["content", "video id", "video"],
    "title":       ["video title", "title"],
    "published":   ["video publish time", "publish time", "published", "date"],
    "duration":    ["duration", "length"],
    "views":       ["views"],
    "impressions": ["impressions"],
    "ctr":         ["impressions clickthrough rate", "impressions ctr", "ctr", "clickthrough rate"],
    "avd":         ["average view duration", "avg view duration", "avd"],
    "apv":         ["average percentage viewed", "avg percentage viewed", "apv"],
    "subs":        ["subscribers", "subscribers gained"],
    "watch_hours": ["watch time hours", "watch time"],
}
SHORT_MAX = 180
DATE_FORMATS = ["%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]
FIX = {
    "PACKAGING": "Good videos nobody clicked. Retitle and re-thumbnail the two best of these with /yt-package, "
                 "then run a test with /yt-test before touching anything else.",
    "RETENTION": "People click and leave. The packaging is fine; the first 30 seconds are not delivering what it "
                 "promised. Export retention for the worst two and run /yt-retention.",
    "TOPIC":     "Neither the click nor the watch is landing. The fix is upstream of the script: run /yt-viral on "
                 "your niche and pick the next three ideas from what is outperforming there.",
    "WORKING":   "At least half of your recent videos are above your own medians on both. Do not change the formula; make more of "
                 "the top three and cut the Shorts from them.",
}


def norm(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (h or "").lower()).strip()


def map_columns(header: List[str]) -> Dict[str, int]:
    h = [norm(x) for x in header]
    out: Dict[str, int] = {}
    for field, names in FIELDS.items():
        for name in names:
            if name in h and h.index(name) not in out.values():
                out[field] = h.index(name)
                break
        else:
            for i, col in enumerate(h):
                if col and i not in out.values() and any(col.startswith(n) for n in names):
                    out[field] = i
                    break
    return out


def num(v: Any) -> Optional[float]:
    s = str(v or "").strip().replace(",", "").replace("%", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None          # "nan" and "inf" parse as floats; they are not data


def seconds(v: Any) -> Optional[float]:
    """613, 10:13 or 0:10:13 -> seconds."""
    s = str(v or "").strip()
    if not s:
        return None
    if ":" in s:
        try:
            parts = [float(p) for p in s.split(":")]
        except ValueError:
            return None
        total = 0.0
        for p in parts:
            total = total * 60 + p
        return total
    return num(s)


def parse_date(v: Any) -> Optional[datetime]:
    s = str(v or "").strip()
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def classify(title: str) -> str:
    best, hits = "Unclassified", 0
    for f in FORMULAS:
        n = sum(1 for p in f.get("match", []) if re.search(p, title, re.I))
        if n > hits:
            best, hits = f["name"], n
    return best


def read(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return []
    cols = map_columns(rows[0])
    if "views" not in cols:
        raise ValueError("no Views column found. Is this the Advanced mode -> Content export?")
    vids = []
    for raw in rows[1:]:
        get = lambda f: raw[cols[f]] if f in cols and cols[f] < len(raw) else ""
        title = str(get("title")).strip()
        if norm(get("id")) == "total" or norm(title) == "total" or not any(c.strip() for c in raw):
            continue
        views = num(get("views"))
        if views is None:
            continue
        dur = seconds(get("duration"))
        avd = seconds(get("avd"))
        apv = num(get("apv"))
        if apv is None and avd is not None and dur:
            apv = avd / dur * 100
        vids.append({"id": str(get("id")).strip(), "title": title or str(get("id")).strip(), "views": views,
                     "published": parse_date(get("published")), "duration": dur,
                     "impressions": num(get("impressions")), "ctr": num(get("ctr")), "avd": avd, "apv": apv,
                     "subs": num(get("subs"))})
    return vids


def median_of(vals: List[Optional[float]]) -> Optional[float]:
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else None


def analyse(vids: List[Dict[str, Any]], include_shorts: bool = False, last: int = 10) -> Dict[str, Any]:
    shorts = [v for v in vids if v["duration"] is not None and v["duration"] <= SHORT_MAX]
    short_ids = {id(v) for v in shorts}
    pool = vids if include_shorts else [v for v in vids if id(v) not in short_ids]
    if not pool:
        return {"videos": [], "shorts_excluded": len(shorts), "medians": {}, "recent": [], "fix": None,
                "quadrants": {}, "groups": []}
    med = {"views": median_of([v["views"] for v in pool]), "ctr": median_of([v["ctr"] for v in pool]),
           "apv": median_of([v["apv"] for v in pool])}
    for v in pool:
        v["multiple"] = v["views"] / med["views"] if med["views"] else None
        v["subs_per_1k"] = (v["subs"] or 0) * 1000 / v["views"] if v["views"] and v["subs"] is not None else None
        v["formula"] = classify(v["title"])
        if v["ctr"] is None or v["apv"] is None or med["ctr"] is None or med["apv"] is None:
            v["quadrant"] = None
        else:
            hi_c, hi_a = v["ctr"] >= med["ctr"], v["apv"] >= med["apv"]
            v["quadrant"] = ("WORKING" if hi_c and hi_a else "RETENTION" if hi_c else
                             "PACKAGING" if hi_a else "TOPIC")
    dated = sorted(pool, key=lambda v: v["published"] or datetime.min, reverse=True)
    recent = dated[:last]
    quads: Dict[str, int] = {}
    for v in recent:
        if v["quadrant"]:
            quads[v["quadrant"]] = quads.get(v["quadrant"], 0) + 1
    problems = {k: n for k, n in quads.items() if k != "WORKING"}
    fix = None
    if quads:
        classified = sum(quads.values())
        if problems and quads.get("WORKING", 0) * 2 < classified:
            order = ["PACKAGING", "RETENTION", "TOPIC"]          # ties go to the cheapest fix
            fix = max(problems, key=lambda k: (problems[k], -order.index(k)))
        else:
            fix = "WORKING"
    groups = []
    for key, label, fn in (
        ("formula", "title formula", lambda v: v["formula"]),
        ("number", "number in title", lambda v: "has a number" if re.search(r"\d", v["title"]) else "no number"),
        ("tlen", "title length", lambda v: "60 chars or less" if len(v["title"]) <= 60 else "over 60"),
        ("dur", "duration", lambda v: None if v["duration"] is None else
         "under 8 min" if v["duration"] < 480 else "8-15 min" if v["duration"] <= 900 else "over 15 min"),
    ):
        buckets: Dict[str, List[float]] = {}
        for v in pool:
            g = fn(v)
            if g is not None and v["multiple"] is not None:
                buckets.setdefault(g, []).append(v["multiple"])
        for g, ms in buckets.items():
            rest = [v["multiple"] for v in pool if v["multiple"] is not None and fn(v) is not None and fn(v) != g]
            if len(ms) >= 3 and len(rest) >= 3:
                a, b = statistics.median(ms), statistics.median(rest)
                if b and (a / b >= 1.5 or a / b <= 0.67):
                    groups.append({"dimension": label, "group": g, "n": len(ms), "median_multiple": round(a, 2),
                                   "rest": round(b, 2), "ratio": round(a / b, 2)})
    groups.sort(key=lambda g: -abs(g["ratio"] - 1) * min(g["n"], 10))
    return {"videos": pool, "shorts_excluded": 0 if include_shorts else len(shorts), "medians": med,
            "recent": recent, "fix": fix, "quadrants": quads, "groups": groups}


def render(a: Dict[str, Any]) -> None:
    vids, med = a["videos"], a["medians"]
    print(f"\n  CHANNEL  ·  {len(vids)} videos" + (f"  ·  {a['shorts_excluded']} Shorts left out" if a["shorts_excluded"] else ""))
    print("  " + "=" * 76)
    mc = f"{med['ctr']:.1f}%" if med.get("ctr") is not None else "n/a"
    ma = f"{med['apv']:.1f}%" if med.get("apv") is not None else "n/a"
    print(f"  your medians: {med['views']:,.0f} views · CTR {mc} · APV {ma}\n")
    ranked = sorted(vids, key=lambda v: -(v["multiple"] or 0))
    print("  OUTLIERS (views over your own median)")
    for v in ranked[:5]:
        print(f"    {v['multiple'] or 0:5.2f}x  {v['views']:>9,.0f}  {v['title'][:52]:<52}  {v['formula']}")
    print("\n  RECENT, BY QUADRANT")
    for v in a["recent"]:
        q = v["quadrant"] or "n/a"
        c = f"{v['ctr']:.1f}%" if v["ctr"] is not None else "  -  "
        p = f"{v['apv']:.0f}%" if v["apv"] is not None else " - "
        print(f"    {q:<10} CTR {c:>6}  APV {p:>4}  {v['multiple'] or 0:5.2f}x  {v['title'][:46]}")
    if a["groups"]:
        print("\n  WHAT SEPARATES (median multiple vs the rest)")
        for g in a["groups"][:4]:
            word = "solid" if g["n"] >= 10 else "moderate" if g["n"] >= 5 else "weak"
            print(f"    {g['dimension']} = {g['group']}: {g['median_multiple']}x vs {g['rest']}x "
                  f"({g['ratio']}x). n={g['n']}, {word}.")
    print("\n  THE ONE FIX")
    if a["fix"] is None:
        print("    Not enough columns to diagnose. Add Impressions click-through rate and Average percentage viewed "
              "to the export and run it again.")
    else:
        counts = ", ".join(f"{k} {n}" for k, n in sorted(a["quadrants"].items(), key=lambda kv: -kv[1]))
        print(f"    {a['fix']}  ({counts} across the last {len(a['recent'])})")
        print(f"    {FIX[a['fix']]}")
    if len(vids) < 10:
        print(f"\n    {len(vids)} videos is a thin sample. Treat this as a direction, not a verdict.")
    elif len(vids) < 3 * len(a["recent"]):
        print(f"\n    Only {len(vids)} videos of history for the last {len(a['recent'])} to be compared against. "
              "Export a longer date range for a sharper read.")
    print("")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Read a Studio content export and name the one fix.")
    ap.add_argument("input")
    ap.add_argument("--last", type=int, default=10, help="how many recent videos decide the fix (default 10)")
    ap.add_argument("--include-shorts", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.last < 1:
        print("--last must be at least 1", file=sys.stderr)
        return 2
    try:
        vids = read(args.input)
    except (OSError, ValueError) as e:
        print(f"could not read {args.input}: {e}", file=sys.stderr)
        return 2
    if not vids:
        print("no video rows found", file=sys.stderr)
        return 2
    a = analyse(vids, args.include_shorts, args.last)
    if not a["videos"]:
        print("every row is a Short. Run again with --include-shorts.", file=sys.stderr)
        return 2
    if args.json:
        clean = lambda v: {k: (x.isoformat() if isinstance(x, datetime) else x) for k, x in v.items()}
        print(json.dumps({"medians": a["medians"], "fix": a["fix"], "quadrants": a["quadrants"],
                          "groups": a["groups"], "shorts_excluded": a["shorts_excluded"],
                          "videos": [clean(v) for v in a["videos"]]}, indent=1, default=str))
        return 0
    render(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
