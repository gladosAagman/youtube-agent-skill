"""Tests for the v2 tools shared across the three packs: voice.py, plan2ics.py
and (X and LinkedIn) targets.py. Normal inputs, then the edge cases: empty
input, malformed lines, injection attempts, boundaries."""

from __future__ import annotations

import csv
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")
P = "yt"
for sub in (f"{P}-voice", f"{P}-plan", f"{P}-engage"):
    sys.path.insert(0, os.path.join(SK, sub))

import plan2ics    # noqa: E402
import voice       # noqa: E402

HAS_TARGETS = os.path.exists(os.path.join(SK, f"{P}-engage", "targets.py"))
targets = importlib.import_module("targets") if HAS_TARGETS else None

SAMPLES = """I shipped the pricing page on Tuesday. Conversions went from 2.1% to 3.4%, and I didn't touch the copy.
---
Most people won't tell you this. Your first 1,000 customers come from conversations, not campaigns.
---
I've been writing once a day for 90 days. Here's what moved: replies. That's it.
---
We lost 2 of 31 clients when I raised prices 40%. I'd do it again.
---
Don't hire before you've done the job yourself for a month. I learned that at $9,000.
"""
MACHINE = ("Moreover, it is crucial to leverage robust synergies — we must delve deeply into the tapestry "
           "of modern growth strategies today. \U0001F680 It is not merely a trend; it is a paradigm shift for "
           "every organisation that wishes to remain competitive.")


def tmp(text, suffix=".txt"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def run(tool, *args, stdin=None):
    return subprocess.run([sys.executable, os.path.join(SK, tool), *args], input=stdin,
                          capture_output=True, text=True, timeout=60)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.profile = voice.build_profile(voice.load_samples([tmp(SAMPLES)]))

    def test_profile_shape(self):
        self.assertEqual(self.profile["samples"], 5)
        self.assertGreater(self.profile["metrics"]["contractions"]["mean"], 2)
        self.assertEqual(self.profile["metrics"]["emoji"]["mean"], 0)

    def test_own_writing_matches(self):
        self.assertEqual(voice.check(self.profile, SAMPLES.split("---")[0])["verdict"] != "DRIFT", True)

    def test_machine_text_drifts_with_hard_flags(self):
        res = voice.check(self.profile, MACHINE)
        self.assertEqual(res["verdict"], "DRIFT")
        joined = " ".join(res["hard"])
        self.assertIn("emoji", joined)
        self.assertIn("em dash", joined)

    def test_short_draft_skips_rhythm(self):
        res = voice.check(self.profile, "Shipped it.")
        skipped = [r for r in res["rows"] if r["score"] is None]
        self.assertTrue(skipped)

    def test_captions_are_stripped(self):
        srt = tmp("1\n00:00:00,000 --> 00:00:02,000\nHello there.\n\n2\n00:00:02,500 --> 00:00:04,000\n"
                  "It's a test.\n", ".srt")
        self.assertEqual(voice.load_samples([srt]), ["Hello there. It's a test."])

    def test_empty_features_do_not_crash(self):
        f = voice.features("")
        self.assertEqual(f["words"], 0)

    def test_cli_save_and_check(self):
        prof = tmp("", ".json")
        self.assertEqual(run(f"{P}-voice/voice.py", tmp(SAMPLES), "--save", prof).returncode, 0)
        self.assertEqual(run(f"{P}-voice/voice.py", "--profile", prof, "--check", tmp(MACHINE)).returncode, 1)
        self.assertEqual(run(f"{P}-voice/voice.py", "--profile", prof, "--check", "-", stdin=MACHINE).returncode, 1)

    def test_cli_bad_inputs_exit_2(self):
        self.assertEqual(run(f"{P}-voice/voice.py").returncode, 2)
        self.assertEqual(run(f"{P}-voice/voice.py", tmp("   ")).returncode, 2)
        self.assertEqual(run(f"{P}-voice/voice.py", "--profile", tmp("{}", ".json"), "--check", tmp("x")).returncode, 2)


class PlanTests(unittest.TestCase):
    PLAN = """WEEK OF SEP 28
MON  9:00   THREAD  #16 Thread Promise  - the 40 viral posts I read
TUE  8:30am POST    #9  Time Anchor     - proposals, 5 hours to 20 minutes; really
Monitor the replies daily
SAT  -
| Wed | Long | 7 Thumbnail Styles Tested | the one that won |
Sunday 12pm STORY the email
Thursday 12am late one
Friday 25:00 not a time
DAILY  20 replies
"""

    def test_parses_days_times_and_skips_noise(self):
        slots = plan2ics.parse_plan(self.PLAN)
        got = [(s.weekday, s.hour, s.minute) for s in slots]
        self.assertEqual(got, [(0, 9, 0), (1, 8, 30), (2, None, 0), (6, 12, 0), (3, 0, 0), (4, None, 0)])
        self.assertTrue(all("Monitor" not in s.summary for s in slots))

    def test_ics_is_valid_shape(self):
        slots = plan2ics.parse_plan(self.PLAN)
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        ics = plan2ics.to_ics(slots, date(2026, 9, 28), now=now, tz="Europe/London")
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(ics.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(ics.count("BEGIN:VEVENT"), len(slots))
        self.assertIn("DTSTART;TZID=Europe/London:20260928T090000", ics)
        self.assertIn("DTSTART;VALUE=DATE:20260930", ics)
        self.assertIn("\\;", ics)                         # the ; in the summary is escaped
        for line in ics.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_week_start_on_any_day(self):
        self.assertEqual(plan2ics.date_for(date(2026, 9, 30), 0), date(2026, 10, 5))
        self.assertEqual(plan2ics.default_week(date(2026, 9, 28)), date(2026, 9, 28))
        self.assertEqual(plan2ics.default_week(date(2026, 9, 29)), date(2026, 10, 5))

    def test_fold_keeps_utf8_whole(self):
        line = "SUMMARY:" + "é" * 80
        for part in plan2ics.fold(line).split("\r\n "):
            part.encode("utf-8").decode("utf-8")
            self.assertLessEqual(len(part.encode("utf-8")), 75)

    def test_cli_errors(self):
        p = tmp(self.PLAN, ".md")
        self.assertEqual(run(f"{P}-plan/plan2ics.py", p, "--week", "2026-13-01").returncode, 2)
        self.assertEqual(run(f"{P}-plan/plan2ics.py", p, "--tz", "Not/AZone").returncode, 2)
        self.assertEqual(run(f"{P}-plan/plan2ics.py", p, "--tz", "../../etc/passwd").returncode, 2)
        self.assertEqual(run(f"{P}-plan/plan2ics.py", tmp("nothing here")).returncode, 1)
        self.assertEqual(run(f"{P}-plan/plan2ics.py", p, "--week", "2026-09-28", "--dry-run").returncode, 0)


@unittest.skipUnless(HAS_TARGETS, "no engagement ledger in this pack")
class TargetsTests(unittest.TestCase):
    def setUp(self):
        self.ledger = tmp("", ".csv")
        os.unlink(self.ledger)
        self.who = "@sarahbuilds" if targets.HANDLE_MODE else "Sarah Chen"

    def add(self, who, tier="reach", note="", when=None):
        args = ["--ledger", self.ledger, "add", who, "--tier", tier, "--note", note]
        if when:
            args += ["--date", when]
        return run(f"{P}-engage/targets.py", *args)

    def test_add_and_report(self):
        for _ in range(3):
            self.assertEqual(self.add(self.who).returncode, 0)
        rep = targets.report(targets.read_ledger(self.ledger), 7)
        self.assertEqual(rep["total"], 3)
        self.assertEqual(rep["people"], 1)

    def test_concentration_warning(self):
        rows = [{"date": date.today().isoformat(), "who": w, "tier": "reach", "note": ""}
                for w in ["a", "a", "a", "a", "b", "b", "b", "c", "c", "c", "d", "e"]]
        rep = targets.report(rows, 7)
        self.assertTrue(any("3 people" in w for w in rep["warnings"]))

    def test_formula_injection_is_neutralised_and_round_trips(self):
        self.assertEqual(self.add(self.who, note="=HYPERLINK(\"http://evil\")").returncode, 0)
        with open(self.ledger, encoding="utf-8") as fh:
            raw = list(csv.reader(fh))
        self.assertTrue(raw[1][3].startswith("'="))
        self.assertTrue(targets.read_ledger(self.ledger)[0]["note"].startswith("=HYPERLINK"))

    def test_rejects_bad_input(self):
        self.assertEqual(self.add("").returncode, 2)
        self.assertEqual(self.add(self.who, when="2999-01-01").returncode, 2)
        self.assertEqual(self.add(self.who, when="yesterday").returncode, 2)
        if targets.HANDLE_MODE:
            self.assertEqual(self.add("@this_handle_is_far_too_long").returncode, 2)
            self.assertEqual(self.add("no spaces allowed").returncode, 2)

    def test_due_orders_never_first(self):
        self.add(self.who, when="2026-01-01")
        other = "@devon_k" if targets.HANDLE_MODE else "Devon K"
        roster = tmp(f"{self.who},reach\n{other},peer\n# comment\n\n")
        out = targets.due(targets.read_ledger(self.ledger), targets.read_roster(roster))
        self.assertIsNone(out[0]["days"])
        self.assertEqual(out[1]["last"], "2026-01-01")

    def test_corrupt_rows_are_skipped(self):
        with open(self.ledger, "w", encoding="utf-8") as fh:
            fh.write("date,who,tier,note\nnot-a-date,x,reach,\n2026-01-01,,reach,\n")
        self.assertEqual(targets.read_ledger(self.ledger), [])


if __name__ == "__main__":
    unittest.main()
