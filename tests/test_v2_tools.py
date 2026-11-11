"""Tests for the YouTube v2 tools: channel.py, abtest.py, ratecard.py, preflight.py."""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")
for sub in ("yt-audit", "yt-test", "yt-sponsor", "yt-preflight"):
    sys.path.insert(0, os.path.join(SK, sub))

import abtest      # noqa: E402
import channel     # noqa: E402
import preflight   # noqa: E402
import ratecard    # noqa: E402


def tmp(text, suffix=".txt"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def run(tool, *args):
    return subprocess.run([sys.executable, os.path.join(SK, tool), *args], capture_output=True, text=True,
                          timeout=60)


HEADER = ["Content", "Video title", "Video publish time", "Duration", "Views", "Impressions",
          "Impressions click-through rate (%)", "Average view duration", "Average percentage viewed (%)",
          "Subscribers"]


def export(rows):
    path = tmp("", ".csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerow(["Total", "", "", "", "999999", "", "", "", "", ""])
        for r in rows:
            w.writerow(r)
    return path


def packaging_channel():
    """Twenty older videos spread evenly around the channel's norm, then ten
    recent ones that still hold attention but stopped getting clicked. The
    recent drift is a packaging problem."""
    rows = []
    for i in range(20):
        ctr = 4.0 + (i % 5) * 0.5           # 4.0 .. 6.0
        apv = 40.0 + (i % 4) * 5.0          # 40 .. 55
        rows.append([f"old{i}", f"Older video {i}", f"Jun {i + 1}, 2026", 600, 12000 + i * 300, 100000, ctr,
                     "0:05:00", apv, 10])
    for i in range(10):
        ctr = 2.5 + (i % 3) * 0.3           # well under the norm
        apv = 56.0 + (i % 3) * 2.0          # above the norm
        rows.append([f"v{i}", f"Recent video {i}", f"Sep {i + 1}, 2026", 600, 9000 + i * 100, 100000, ctr,
                     "0:05:00", apv, 10])
    rows.append(["s1", "A short", "Sep 20, 2026", 40, 900000, 1000000, 12.0, "0:00:35", 90.0, 500])
    return rows


class ChannelTests(unittest.TestCase):
    def test_reads_export_skips_total(self):
        vids = channel.read(export(packaging_channel()))
        self.assertEqual(len(vids), 31)
        self.assertFalse(any(v["title"] == "Total" for v in vids))

    def test_shorts_excluded_and_fix_is_packaging(self):
        a = channel.analyse(channel.read(export(packaging_channel())))
        self.assertEqual(a["shorts_excluded"], 1)
        self.assertEqual(len(a["videos"]), 30)
        self.assertEqual(a["fix"], "PACKAGING")
        self.assertEqual(a["quadrants"].get("PACKAGING"), 10)

    def test_working_needs_half(self):
        rows = [[f"v{i}", f"t{i}", f"Sep {i + 1}, 2026", 600, 1000, 10000, 9.0 if i < 5 else 1.0, "0:05:00",
                 60.0 if i < 5 else 59.0, 0] for i in range(10)]
        a = channel.analyse(channel.read(export(rows)))
        self.assertEqual(a["quadrants"].get("WORKING"), 5)
        self.assertEqual(a["fix"], "WORKING")

    def test_duration_formats(self):
        self.assertEqual(channel.seconds("613"), 613)
        self.assertEqual(channel.seconds("10:13"), 613)
        self.assertEqual(channel.seconds("0:10:13"), 613)
        self.assertIsNone(channel.seconds("abc"))

    def test_zero_views_does_not_crash(self):
        rows = [[f"v{i}", f"t{i}", f"Sep {i + 1}, 2026", 600, 0, 0, "", "", "", ""] for i in range(5)]
        self.assertEqual(run("yt-audit/channel.py", export(rows)).returncode, 0)

    def test_bad_inputs(self):
        self.assertEqual(run("yt-audit/channel.py", tmp("a,b\n1,2\n", ".csv")).returncode, 2)
        self.assertEqual(run("yt-audit/channel.py", "/nonexistent.csv").returncode, 2)
        only_shorts = [["s", "short", "Sep 1, 2026", 30, 100, 1000, 5, "0:00:20", 70, 0]]
        self.assertEqual(run("yt-audit/channel.py", export(only_shorts)).returncode, 2)


class ABTestTests(unittest.TestCase):
    def test_known_significant_result(self):
        r = abtest.compare(("A", 12400, 496), ("B", 11900, 571), 0.05)
        self.assertEqual(r["verdict"], "WINNER")
        self.assertAlmostEqual(r["p"], 0.0024, places=3)

    def test_small_sample_not_yet_even_if_significant(self):
        r = abtest.compare(("A", 300, 9), ("B", 300, 30), 0.05)
        self.assertLess(r["p"], 0.05)
        self.assertEqual(r["verdict"], "NOT YET")

    def test_identical_is_no_call(self):
        self.assertEqual(abtest.compare(("A", 5000, 200), ("B", 5000, 200), 0.05)["verdict"], "NO CALL")

    def test_loser(self):
        self.assertEqual(abtest.compare(("A", 20000, 1000), ("B", 20000, 700), 0.05)["verdict"], "LOSER")

    def test_inverse_normal(self):
        self.assertAlmostEqual(abtest.z_for(0.05), 1.959964, places=4)

    def test_required_n_is_sane(self):
        n = abtest.required_n(0.04, 0.05, 0.05)
        self.assertTrue(6000 < n < 8000, n)
        self.assertIsNone(abtest.required_n(0.04, 0.04, 0.05))

    def test_validation(self):
        for bad in ("A:10:20", "A:0:0", "A:-1:0", "A:x:1", "noparts", "<b>:10:1"):
            with self.assertRaises(ValueError, msg=bad):
                abtest.parse_variant(bad)
        self.assertEqual(abtest.parse_variant("Face left:1,200:48"), ("Face left", 1200, 48))

    def test_cli(self):
        self.assertEqual(run("yt-test/abtest.py", "--variant", "A:12400:496", "--variant", "B:11900:571").returncode, 0)
        self.assertEqual(run("yt-test/abtest.py", "--variant", "A:100:1").returncode, 2)
        self.assertEqual(run("yt-test/abtest.py", "--variant", "A:100:1", "--variant", "A:100:2").returncode, 2)
        self.assertEqual(run("yt-test/abtest.py", tmp("name,impressions,clicks\nA,1000,40\nB,1000,60\n", ".csv"),
                             "--json").returncode, 0)


class RatecardTests(unittest.TestCase):
    def test_median_not_mean(self):
        c = ratecard.card([20000, 21000, 22000, 23000, 500000], 20, 30)
        self.assertEqual(c["median_views"], 22000)
        self.assertEqual(c["flat_fee_low"], 440)
        self.assertEqual(c["flat_fee_high"], 660)
        self.assertGreater(c["mean_over_median"], 1.3)

    def test_percentiles(self):
        self.assertEqual(ratecard.percentile([1, 2, 3, 4, 5], 0.25), 2)
        self.assertEqual(ratecard.percentile([10], 0.75), 10)

    def test_refuses_bad_input(self):
        for views, lo, hi in (([1, 2, 3], 1, 2), ([1, 2, 3, 4, 5], 0, 2), ([1, 2, 3, 4, 5], 3, 2),
                              ([1, 2, 3, 4, -5], 1, 2), ([1, 2, 3, 4, math.nan], 1, 2), ([1, 2, 3, 4, 5], 1, math.inf)):
            with self.assertRaises(ValueError):
                ratecard.card(views, lo, hi)

    def test_cpm_is_required(self):
        self.assertEqual(run("yt-sponsor/ratecard.py", "--views", "1", "2", "3", "4", "5").returncode, 2)


DESC_OK = "I tested 7 thumbnail styles for 30 days.\nTemplate below.\n\n0:00 Intro\n0:20 The test\n1:10 Results\n"


class PreflightTests(unittest.TestCase):
    def test_chapters_rules(self):
        self.assertEqual(preflight.chapters(DESC_OK)["problems"], [])
        self.assertTrue(preflight.chapters("0:05 a\n0:20 b\n0:40 c")["problems"])
        self.assertTrue(preflight.chapters("0:00 a\n0:20 b")["problems"])
        self.assertTrue(preflight.chapters("0:00 a\n0:05 b\n0:40 c")["problems"])
        self.assertIsNone(preflight.chapters("no timestamps here"))
        self.assertEqual(preflight.chapters("0:00 a\n1:00:00 b\n1:10:00 c")["problems"], [])

    def test_query_stemming(self):
        res = preflight.query_test(["thumbnail test", "youtube tips"], "I Tested 7 Thumbnails", "")
        self.assertEqual(res[0]["missing"], [])
        self.assertEqual(res[1]["missing"], ["youtube", "tips"])

    def test_hook_line_is_first_sentence(self):
        self.assertEqual(preflight.hook_line("One two three. Four five."), "One two three.")

    def test_full_run(self):
        r = preflight.run("I Tested 7 Thumbnail Styles for 30 Days", "ONE WON",
                          "97% of thumbnails fail at feed size. Here is the one that did not.", DESC_OK,
                          ["thumbnail test"])
        stages = {s["stage"]: s["status"] for s in r["stages"]}
        self.assertEqual(set(stages), {"PACKAGE", "HOOK", "RUNTIME", "QUERIES", "CHAPTERS"})
        self.assertEqual(stages["CHAPTERS"], "PASS")

    def test_cli(self):
        tool = "yt-preflight/preflight.py"
        self.assertEqual(run(tool, "--title", "  ").returncode, 2)
        self.assertEqual(run(tool, "--title", "x", "--script", "/nonexistent").returncode, 2)
        self.assertIn(run(tool, "--title", "I Tried 7 Thumbnail Styles for 30 Days", "--json").returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()
