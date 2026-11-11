#!/usr/bin/env python3
"""
plan2ics.py - turn the weekly plan into calendar reminders, so the plan
actually gets run.

Scheduling tools post for you. This pack never posts, on purpose, so the gap
it leaves is the reminder: the plan sits in plan.md and Tuesday goes by. This
reads the plan and writes a standard .ics file. Import it into Google
Calendar, Apple Calendar or Outlook and each slot becomes an event with the
angle and the hook formula in it. You still post by hand.

It reads any line that starts with a day name, with or without a time:

  TUE  8:30   POST    #9  Time Anchor     - proposals, 5 hours to 20 minutes
  THU  8:00am  OPINION  #1  Contrarian    - why we killed the discovery call
  | Wed | Long | 7 Thumbnail Styles Tested | the one that won |      (markdown table rows)
  SAT  -                                                               (skipped: nothing planned)

A line with a time becomes a timed event (24-hour unless it says am/pm). A
line without one becomes an all-day event. Anything else in the file is
ignored, so the plan can keep its headers and notes.

Usage
  python3 plan2ics.py ~/.claude/youtube/plan.md --week 2026-09-28 -o week.ics
  python3 plan2ics.py plan.md --tz America/New_York --remind 15 --minutes 30
  python3 plan2ics.py plan.md --dry-run          # list what it found, write nothing

--week is the first day of the plan's week (default: the coming Monday, or
today if today is Monday). Each line lands on the first date on or after it
with that weekday.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

PRODID = "-//youtube-agent//plan2ics//EN"
DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
LINE_RE = re.compile(
    r"^\s*\|?\s*(mon|tue|wed|thu|fri|sat|sun)"
    r"(?:day|s|sday|nesday|r|rs|rsday|urday)?\.?(?=[\s|:,]|$)\s*[|:,]?\s*(.*)$", re.IGNORECASE)
TIME_RE = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?=[\s|,]|$)", re.IGNORECASE)
NOTE = "From your weekly plan. Nothing is posted automatically: this is a reminder to post it yourself."


@dataclass
class Slot:
    weekday: int
    hour: Optional[int]
    minute: int
    summary: str
    source_line: int


def parse_time(text: str) -> Tuple[Optional[Tuple[int, int]], str]:
    """Return ((hour, minute) or None, remainder). A bare number is not a time
    unless it has a colon or am/pm, so '#16' or '3 Shorts' are never read as one."""
    m = TIME_RE.match(text)
    if not m or (m.group(2) is None and m.group(3) is None):
        return None, text
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm:
        if not 1 <= hour <= 12:
            return None, text
        hour = (hour % 12) + (12 if ampm == "pm" else 0)
    if hour > 23 or minute > 59:
        return None, text
    return (hour, minute), text[m.end():]


def clean_summary(text: str) -> str:
    parts = [p.strip() for p in text.split("|")]
    text = " · ".join(p for p in parts if p)
    return re.sub(r"\s{2,}", "  ", text).strip(" -·")


def parse_plan(text: str) -> List[Slot]:
    slots: List[Slot] = []
    for n, raw in enumerate(text.splitlines(), 1):
        m = LINE_RE.match(raw)
        if not m:
            continue
        rest = m.group(2).strip().lstrip("|").strip()
        t, rest = parse_time(rest)
        summary = clean_summary(rest)
        if not summary or set(summary) <= set("-–· "):
            continue
        slots.append(Slot(DAYS[m.group(1).lower()], t[0] if t else None, t[1] if t else 0, summary, n))
    return slots


def default_week(today: Optional[date] = None) -> date:
    today = today or date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7)


def date_for(week_start: date, weekday: int) -> date:
    return week_start + timedelta(days=(weekday - week_start.weekday()) % 7)


def escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line: str) -> str:
    """RFC 5545: lines over 75 octets are folded, never inside a UTF-8 sequence."""
    out, cur, size = [], "", 0
    for ch in line:
        b = len(ch.encode("utf-8"))
        limit = 75 if not out else 74          # continuation lines start with a space
        if size + b > limit:
            out.append(cur)
            cur, size = ch, b
        else:
            cur += ch
            size += b
    out.append(cur)
    return "\r\n ".join(out)


def to_ics(slots: List[Slot], week_start: date, minutes: int = 30, remind: Optional[int] = 10,
           tz: Optional[str] = None, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN"]
    for s in slots:
        day = date_for(week_start, s.weekday)
        uid = hashlib.sha1(f"{day.isoformat()}|{s.hour}|{s.minute}|{s.summary}".encode("utf-8")).hexdigest()
        lines += ["BEGIN:VEVENT", f"UID:{uid}@youtube-agent", f"DTSTAMP:{stamp}"]
        if s.hour is None:
            lines.append(f"DTSTART;VALUE=DATE:{day:%Y%m%d}")
            lines.append(f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}")
        else:
            start = datetime(day.year, day.month, day.day, s.hour, s.minute)
            end = start + timedelta(minutes=minutes)
            tzp = f";TZID={tz}" if tz else ""
            lines.append(f"DTSTART{tzp}:{start:%Y%m%dT%H%M%S}")
            lines.append(f"DTEND{tzp}:{end:%Y%m%dT%H%M%S}")
        lines.append(f"SUMMARY:{escape('YouTube: ' + s.summary)}")
        lines.append(f"DESCRIPTION:{escape(NOTE)}")
        if remind is not None and remind >= 0 and s.hour is not None:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{escape(s.summary)}",
                      f"TRIGGER:-PT{remind}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in lines) + "\r\n"


def valid_tz(name: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_+\-/]{1,64}", name):
        return False
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(name)
        return True
    except Exception:
        return False


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Turn a weekly plan into calendar reminders (.ics).")
    ap.add_argument("plan", help="plan.md, or - for stdin")
    ap.add_argument("--week", help="first day of the plan's week, YYYY-MM-DD (default: coming Monday)")
    ap.add_argument("-o", "--out", help="write the .ics here (default: stdout)")
    ap.add_argument("--minutes", type=int, default=30, help="length of a timed event (default 30)")
    ap.add_argument("--remind", type=int, default=10, help="alert this many minutes before (-1 for none)")
    ap.add_argument("--tz", help="IANA timezone for the times, e.g. Europe/London (default: floating local time)")
    ap.add_argument("--dry-run", action="store_true", help="list the slots found and write nothing")
    args = ap.parse_args(argv)

    try:
        week = date.fromisoformat(args.week) if args.week else default_week()
    except ValueError:
        print(f"--week must be YYYY-MM-DD, got {args.week!r}", file=sys.stderr)
        return 2
    if not 1 <= args.minutes <= 24 * 60:
        print("--minutes must be between 1 and 1440", file=sys.stderr)
        return 2
    if args.tz and not valid_tz(args.tz):
        print(f"unknown timezone {args.tz!r}. Use an IANA name like America/New_York.", file=sys.stderr)
        return 2
    try:
        if args.plan == "-":
            text = sys.stdin.read()
        else:
            with open(args.plan, encoding="utf-8") as fh:
                text = fh.read()
    except OSError as e:
        print(f"could not read plan: {e}", file=sys.stderr)
        return 2

    slots = parse_plan(text)
    if not slots:
        print("no day lines found. Each slot needs to start with a day name (MON, Tue, Wednesday...).",
              file=sys.stderr)
        return 1
    if args.dry_run or args.out:
        print(f"\n  {len(slots)} slot(s), week of {week:%a %b %d %Y}\n", file=sys.stderr)
        for s in slots:
            d = date_for(week, s.weekday)
            when = f"{s.hour:02d}:{s.minute:02d}" if s.hour is not None else "all day"
            print(f"    {d:%a %b %d}  {when:<8} {s.summary[:70]}", file=sys.stderr)
        print("", file=sys.stderr)
    if args.dry_run:
        return 0
    ics = to_ics(slots, week, args.minutes, None if args.remind < 0 else args.remind, args.tz)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as fh:
            fh.write(ics)
        print(f"  wrote {args.out}. Import it into your calendar.\n", file=sys.stderr)
    else:
        sys.stdout.write(ics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
