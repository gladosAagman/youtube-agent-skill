#!/usr/bin/env python3
"""preflight.py - everything that can be checked before you hit publish, in one pass.

    python3 preflight.py --title "I Tested 7 Thumbnails for 30 Days" --thumb "ONE WON" \\
        --script script.txt --description description.txt --queries "thumbnail test;youtube ctr"

  PACKAGE      yt-package/title.py      the title and thumbnail as one pairing
  HOOK         yt-script/hookscore.py   the script's opening line (its first sentence)
  RUNTIME      the script at 150 words a minute
  QUERIES      do the title and the first two description lines contain the words
               of each query this video should win (/yt-seo's query test)
  CHAPTERS     if the description has timestamps: 0:00 first, 3+, 10s apart,
               which is what YouTube needs before it will render them
  VOICE        the script against your measured voice, if ~/.claude/youtube/voice.json exists

Every flag is optional except --title. It prints READY or FIX FIRST with the
fixes in order, and changes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("yt-package", "yt-script", "yt-voice"):
    sys.path.insert(0, os.path.join(HERE, "..", sub))

import hookscore   # noqa: E402
import title       # noqa: E402
import voice       # noqa: E402

DEFAULT_PROFILE = os.path.expanduser("~/.claude/youtube/voice.json")
WPM = 150
HOOK_WORDS = 40
PACKAGE_FLOOR = 60
STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "how", "what", "why", "my", "your",
        "with", "vs", "do", "does", "i", "you"}
TS_LINE = re.compile(r"^\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?\s*[-–:|]?\s*(.+)$")


def to_seconds(ts: str) -> int:
    total = 0
    for p in ts.split(":"):
        total = total * 60 + int(p)
    return total


def chapters(description: str) -> Optional[Dict[str, Any]]:
    stamps = []
    for line in description.splitlines():
        m = TS_LINE.match(line)
        if m:
            stamps.append((to_seconds(m.group(1)), m.group(2).strip()))
    if not stamps:
        return None
    problems = []
    if stamps[0][0] != 0:
        problems.append("the first timestamp must be 0:00")
    if len(stamps) < 3:
        problems.append(f"{len(stamps)} timestamps; YouTube needs at least 3")
    for (a, _), (b, label) in zip(stamps, stamps[1:]):
        if b - a < 10:
            problems.append(f"\"{label[:30]}\" starts {b - a}s after the previous one; 10s is the minimum")
        if b <= a:
            problems.append(f"\"{label[:30]}\" is not after the previous timestamp")
    return {"count": len(stamps), "problems": problems}


def stem(w: str) -> str:
    """Crude, on purpose: enough that "tested" covers "test" and "tips" covers "tip"."""
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf) and not w.endswith("ss"):
            return w[: -len(suf)]
    return w


def query_test(queries: List[str], title_text: str, description: str) -> List[Dict[str, Any]]:
    head = " ".join([ln for ln in description.splitlines() if ln.strip()][:2])
    hay = {stem(w) for w in re.findall(r"[a-z0-9']+", (title_text + " " + head).lower())}
    out = []
    for q in queries:
        words = [w for w in re.findall(r"[a-z0-9']+", q.lower()) if w not in STOP]
        missing = [w for w in words if stem(w) not in hay]
        out.append({"query": q, "missing": missing})
    return out


def hook_line(script: str) -> str:
    """The first sentence of the script, capped at HOOK_WORDS words. hookscore.py
    is tuned on single hook lines, so it is given one."""
    text = " ".join(script.split())
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return " ".join(first.split()[:HOOK_WORDS])


def run(title_text: str, thumb: Optional[str] = None, script: Optional[str] = None,
        description: Optional[str] = None, queries: Optional[List[str]] = None,
        profile_path: Optional[str] = None) -> Dict[str, Any]:
    stages: List[Dict[str, Any]] = []
    fixes: List[str] = []

    t = title.check(title_text, thumb)
    st = "PASS" if t["score"] >= 80 else "WARN" if t["score"] >= PACKAGE_FLOOR else "FAIL"
    stages.append({"stage": "PACKAGE", "status": st, "detail": f"{t['score']}/100, {t['chars']} chars"})
    fixes += [f"PACKAGE {k}: {m}" for k, m in t["issues"]]

    if script:
        words = script.split()
        hook = hook_line(script)
        parts, verdict, name, _ = hookscore.score(hook)
        band = hookscore.band(verdict)
        st = "PASS" if band == "STRONG" else "WARN" if band == "WORKABLE" else "FAIL"
        stages.append({"stage": "HOOK", "status": st, "detail": f"{verdict} {band} · {name}"})
        if st != "PASS":
            low = min(parts, key=parts.get)
            fixes.append(f"HOOK: weakest is {low}. {hookscore.FIX[low]}")
        minutes = len(words) / WPM
        stages.append({"stage": "RUNTIME", "status": "PASS",
                       "detail": f"{len(words):,} words, about {int(minutes)}:{int((minutes % 1) * 60):02d} at {WPM} wpm"})
        path = profile_path or (DEFAULT_PROFILE if os.path.exists(DEFAULT_PROFILE) else None)
        if path:
            try:
                with open(os.path.expanduser(path), encoding="utf-8") as fh:
                    v = voice.check(json.load(fh), script)
                stages.append({"stage": "VOICE", "status": "PASS" if v["verdict"] == "MATCH" else
                               "WARN" if v["verdict"] == "CLOSE" else "FAIL", "detail": f"{v['score']:.1f} {v['verdict']}"})
                fixes += [f"VOICE: {h}" for h in v["hard"]]
            except (OSError, ValueError, KeyError) as e:
                stages.append({"stage": "VOICE", "status": "SKIP", "detail": f"profile unreadable: {e}"})

    if description is not None:
        if queries:
            res = query_test(queries, title_text, description)
            bad = [r for r in res if r["missing"]]
            stages.append({"stage": "QUERIES", "status": "WARN" if bad else "PASS",
                           "detail": f"{len(res) - len(bad)}/{len(res)} queries covered by the title + first 2 lines"})
            fixes += [f"QUERIES: \"{r['query']}\" is missing {', '.join(r['missing'])} from the title and the "
                      "first two description lines" for r in bad]
        ch = chapters(description)
        if ch is not None:
            stages.append({"stage": "CHAPTERS", "status": "FAIL" if ch["problems"] else "PASS",
                           "detail": f"{ch['count']} timestamps" + (", will not render" if ch["problems"] else ", valid")})
            fixes += [f"CHAPTERS: {p}" for p in ch["problems"]]

    return {"ready": not any(s["status"] == "FAIL" for s in stages), "stages": stages, "fixes": fixes}


def render(r: Dict[str, Any], out=sys.stdout) -> None:
    print("\n  PRE-FLIGHT", file=out)
    print("  " + "=" * 64, file=out)
    for s in r["stages"]:
        print(f"    {s['stage']:<9} {s['status']:<5} {s['detail']}", file=out)
    print("  " + "-" * 64, file=out)
    print(f"    {'READY' if r['ready'] else 'FIX FIRST'}", file=out)
    for i, f in enumerate(r["fixes"], 1):
        print(f"    {i}. {f}", file=out)
    print("\n  ship it, or change it?\n", file=out)


def read(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Every pre-publish check in one pass.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--thumb", help="the words on the thumbnail")
    ap.add_argument("--script", help="script or transcript text file")
    ap.add_argument("--description", help="description text file")
    ap.add_argument("--queries", help="the searches this should win, separated by ;")
    ap.add_argument("--profile", help="voice profile JSON")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.title.strip():
        print("--title is empty", file=sys.stderr)
        return 2
    try:
        script, desc = read(args.script), read(args.description)
    except OSError as e:
        print(f"could not read file: {e}", file=sys.stderr)
        return 2
    queries = [q.strip() for q in (args.queries or "").split(";") if q.strip()]
    if queries and desc is None:
        desc = ""
    r = run(args.title, args.thumb, script, desc, queries, args.profile)
    if args.json:
        print(json.dumps(r, indent=1))
    else:
        render(r)
    return 0 if r["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
