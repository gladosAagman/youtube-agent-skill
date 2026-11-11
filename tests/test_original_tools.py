"""Regression tests for the six tools that shipped in v1."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")
for sub in ("yt-script", "yt-package", "yt-edit"):
    sys.path.insert(0, os.path.join(SK, sub))

import deadair     # noqa: E402
import hookscore   # noqa: E402
import title       # noqa: E402

SRT = """1
00:00:00,000 --> 00:00:03,000
Today we talk about thumbnails and titles

2
00:00:04,500 --> 00:00:07,000
um

3
00:00:07,200 --> 00:00:10,000
The first thing about thumbnails is contrast

4
00:00:10,100 --> 00:00:13,000
The first thing about thumbnails is contrast at feed size

5
00:00:15,000 --> 00:00:20,000
Now let us move on to retention graphs and audience

6
00:00:20,500 --> 00:00:26,000
Retention graphs show where the audience leaves

7
00:00:28,000 --> 00:00:34,000
Finally pricing sponsors and money from brand deals

8
00:00:34,500 --> 00:00:40,000
Sponsors pay per thousand views on brand deals
"""


def tmp(text, suffix=".txt"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def run(tool, *args):
    return subprocess.run([sys.executable, os.path.join(SK, tool), *args], capture_output=True, text=True,
                          timeout=60)


class HookscoreTests(unittest.TestCase):
    def test_specific_beats_generic(self):
        _, good, _, _ = hookscore.score("97% of the people who start a channel quit before video 30. "
                                        "Here is what the other 3% do differently.")
        _, bad, _, _ = hookscore.score("Hey guys welcome back to the channel")
        self.assertGreater(good, bad)

    def test_classifies_statistic(self):
        self.assertEqual(hookscore.classify("97% of creators quit before video 30")[0], "The Statistic")

    def test_21_formulas(self):
        self.assertEqual(len(hookscore.FORMULAS), 21)


class TitleTests(unittest.TestCase):
    def test_duplicate_thumbnail_flagged(self):
        r = title.check("I Tried 7 Thumbnail Styles", "THUMBNAIL STYLES")
        self.assertIn("duplicate", [k for k, _ in r["issues"]])

    def test_long_and_vague(self):
        r = title.check("The ultimate insane amazing guide to everything you will ever need to know about YouTube")
        kinds = [k for k, _ in r["issues"]]
        self.assertIn("length", kinds)
        self.assertIn("vague", kinds)

    def test_clean_pairing_scores_high(self):
        self.assertGreaterEqual(title.check("I Tried 7 Thumbnail Styles for 30 Days", "ONE WON")["score"], 80)


class DeadairTests(unittest.TestCase):
    def test_finds_dead_filler_and_repeat(self):
        cues = deadair.load(tmp(SRT, ".srt"))
        self.assertEqual(len(cues), 8)
        r = run("yt-edit/deadair.py", tmp(SRT, ".srt"), "--json")
        kinds = {c["kind"] for c in json.loads(r.stdout)["cuts"]}
        self.assertEqual(kinds, {"DEAD", "FILLER", "REPEAT"})

    def test_parse_ts(self):
        self.assertAlmostEqual(deadair.parse_ts("01:02:03,500"), 3723.5)
        self.assertAlmostEqual(deadair.parse_ts("02:03.5"), 123.5)


class ChaptersTests(unittest.TestCase):
    def test_valid_chapters(self):
        r = run("yt-chapters/chapters.py", tmp(SRT, ".srt"), "--json")
        d = json.loads(r.stdout)
        self.assertTrue(d["valid"])
        self.assertEqual(d["chapters"][0]["start"], 0)


class RetentionTests(unittest.TestCase):
    def test_hook_leak_and_cliff(self):
        csv = "0,100\n5,90\n10,80\n20,74\n30,70\n40,68\n50,60\n60,58\n70,56\n80,52\n90,50\n100,40\n"
        r = run("yt-retention/retention.py", tmp(csv, ".csv"), "--duration", "600", "--json")
        d = json.loads(r.stdout)
        self.assertGreater(d["hook_leak"], 0)
        self.assertTrue(d["cliffs"])


class SwipeTests(unittest.TestCase):
    def test_outlier_and_thin_channel(self):
        rows = [{"channel": "a", "title": t, "views": v} for t, v in
                (("97% of creators quit", 900), ("x", 100), ("y", 120), ("z", 110))]
        rows.append({"channel": "thin", "title": "one", "views": 5})
        d = json.loads(run("yt-viral/swipe.py", tmp(json.dumps(rows), ".json"), "--json").stdout)
        self.assertEqual(d["outliers"][0]["title"], "97% of creators quit")
        self.assertEqual(d["skipped_thin_channels"], [["thin", 1]])


if __name__ == "__main__":
    unittest.main()
