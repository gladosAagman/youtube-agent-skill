#!/usr/bin/env python3
"""abtest.py - is the thumbnail or title test actually decided, or is it noise?

    python3 abtest.py --variant A:12400:496 --variant B:11900:571
    python3 abtest.py results.csv                 # name,impressions,clicks per line
    python3 abtest.py --variant A:900:40 --variant B:880:52 --json

Each variant is NAME:IMPRESSIONS:CLICKS, read off whatever ran the test
(TubeBuddy and similar tools show both; for a manual swap, read them from
Studio for equal windows). The first variant is the control.

It runs a two-sided two-proportion z-test of each challenger against the
control, with the alpha split across challengers (Bonferroni) so a three-way
test is not three chances to fool yourself. Then it says one of three things:

  WINNER    the difference is unlikely to be noise and both arms have 1,000+
            impressions
  NOT YET   and roughly how many more impressions per variant it would take
            to call the difference it is currently showing
  NO CALL   the arms are too close to call at any sample you are likely to get.
            Keep the one that matches the video better.

About YouTube's own Test & Compare: Studio picks its winner on watch time
share, not click-through, and it shows percentages without the counts behind
them. A percentage alone cannot be tested for significance, so this tool
does not pretend to. Use Studio's verdict for Studio's test.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

ALPHA = 0.05
POWER_Z = 0.8416           # z for 80% power
MIN_IMPRESSIONS = 1000
NAME_RE = re.compile(r"^[A-Za-z0-9 _.-]{1,32}$")


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def z_for(p_two_sided: float) -> float:
    """Inverse normal for an upper-tail probability, by bisection. Exact enough here."""
    target = 1.0 - p_two_sided / 2.0
    lo, hi = 0.0, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if phi(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def parse_variant(spec: str) -> Tuple[str, int, int]:
    parts = spec.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError(f"{spec!r}: expected NAME:IMPRESSIONS:CLICKS")
    name, imp_s, clk_s = parts[0].strip(), parts[1].strip().replace(",", ""), parts[2].strip().replace(",", "")
    if not NAME_RE.match(name):
        raise ValueError(f"{name!r}: a variant name is 1-32 letters, digits, spaces, _ . -")
    if not imp_s.isdigit() or not clk_s.isdigit():
        raise ValueError(f"{spec!r}: impressions and clicks must be whole numbers, 0 or more")
    imp, clk = int(imp_s), int(clk_s)
    if imp == 0:
        raise ValueError(f"{name}: zero impressions, nothing to test")
    if clk > imp:
        raise ValueError(f"{name}: {clk} clicks is more than {imp} impressions")
    return name, imp, clk


def required_n(p1: float, p2: float, alpha: float) -> Optional[int]:
    """Impressions per arm to detect p1 vs p2 at `alpha` (two-sided) with 80% power."""
    if p1 == p2:
        return None
    za = z_for(alpha)
    pbar = (p1 + p2) / 2.0
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + POWER_Z * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / (p1 - p2) ** 2))


def compare(control: Tuple[str, int, int], other: Tuple[str, int, int], alpha: float) -> Dict[str, Any]:
    _, n1, c1 = control
    name, n2, c2 = other
    p1, p2 = c1 / n1, c2 / n2
    pool = (c1 + c2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se if se > 0 else 0.0
    p = 2 * (1 - phi(abs(z))) if se > 0 else 1.0
    need = required_n(p1, p2, alpha)
    enough = min(n1, n2) >= MIN_IMPRESSIONS
    if p < alpha and enough:
        verdict, reason = ("WINNER" if p2 > p1 else "LOSER"), "unlikely to be noise"
    elif p < alpha:
        verdict, reason = "NOT YET", f"looks real, but an arm is under {MIN_IMPRESSIONS:,} impressions. Let it run."
    elif need is None or need > 500_000:
        verdict, reason = "NO CALL", "too close to call at any realistic sample. Keep the one that fits the video."
    else:
        verdict = "NOT YET"
        reason = (f"about {need:,} impressions per arm to call this gap "
                  f"({max(0, need - min(n1, n2)):,} more)")
    return {"variant": name, "ctr": round(p2 * 100, 3), "control_ctr": round(p1 * 100, 3),
            "lift_pct": round((p2 - p1) / p1 * 100, 1) if p1 else None, "z": round(z, 3), "p": round(p, 4),
            "alpha": round(alpha, 4), "verdict": verdict, "reason": reason, "needed_per_arm": need,
            "more_needed": max(0, need - min(n1, n2)) if need else None}


def read_file(path: str) -> List[Tuple[str, int, int]]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if not row or not "".join(row).strip() or row[0].strip().lower() in ("name", "variant"):
                continue
            if len(row) < 3:
                raise ValueError(f"line {row!r}: need name,impressions,clicks")
            out.append(parse_variant(":".join(c.strip() for c in row[:3])))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Decide whether a thumbnail/title test is decided.")
    ap.add_argument("input", nargs="?", help="CSV of name,impressions,clicks")
    ap.add_argument("--variant", action="append", default=[], help="NAME:IMPRESSIONS:CLICKS, control first")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not 0 < args.alpha < 0.5:
        print("--alpha must be between 0 and 0.5", file=sys.stderr)
        return 2
    try:
        variants = read_file(args.input) if args.input else []
        variants += [parse_variant(v) for v in args.variant]
    except (OSError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2
    if len(variants) < 2:
        print("need at least two variants (control first)", file=sys.stderr)
        return 2
    if len({v[0] for v in variants}) != len(variants):
        print("variant names must be unique", file=sys.stderr)
        return 2
    alpha = args.alpha / (len(variants) - 1)
    results = [compare(variants[0], v, alpha) for v in variants[1:]]
    if args.json:
        print(json.dumps({"control": variants[0][0], "results": results}, indent=1))
        return 0
    c = variants[0]
    print(f"\n  TEST  ·  control {c[0]}: {c[2]:,} clicks / {c[1]:,} impressions = {c[2] / c[1] * 100:.2f}% CTR")
    print(f"  alpha {args.alpha} split across {len(results)} challenger(s) -> {alpha:.4f} each\n")
    for r, v in zip(results, variants[1:]):
        lift = f"{r['lift_pct']:+.1f}%" if r["lift_pct"] is not None else "n/a"
        print(f"    {v[0]:<10} {r['ctr']:6.2f}% CTR  {lift:>8} vs control   p={r['p']:.4f}   {r['verdict']}")
        print(f"               {r['reason']}")
    print("\n  CTR is the click, not the watch. A thumbnail that wins CTR and loses retention over-promised.")
    print("  Check average view duration for each window before you keep the winner.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
