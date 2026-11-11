#!/usr/bin/env python3
"""
voice.py - measure how you actually write, so voice.md is evidence instead of
a guess, then check any draft against it before it goes out under your name.

Every skill in this pack reads voice.md. Filled in by hand, it describes how
you would like to sound. Measured from your own video transcripts, it describes how you
do sound, and that is the version a reader recognises.

What it measures, per sample, then as a profile (mean and spread):

  sentence length    words per sentence, and how much it varies
  contractions       per 100 words. Models write "do not"; people write "don't"
  person             I / we / you per 100 words
  questions          share of sentences that end in "?"
  exclamations       share of sentences that end in "!"
  casing             share of sentences that start lower-case
  emoji              per 100 words
  em dashes          per 1,000 characters
  numbers            per 100 words, the specificity habit
  length             words and lines per sample

Plus the words that are yours (used in at least two samples, not stop words)
and how you open.

Input: one or more text files. Samples inside a file are separated by a line
containing only ---. Caption files (.srt, .vtt) have their timestamps
stripped first, and each caption file counts as one sample.

Usage
  python3 voice.py samples.txt                           # print the measured profile
  python3 voice.py samples.txt --save ~/.claude/youtube/voice.json
  python3 voice.py --profile ~/.claude/youtube/voice.json --check draft.txt
  python3 voice.py samples.txt --check draft.txt --json

--check exits 0 when the draft matches the profile and 1 when it drifts, so
it can sit in a pre-flight script. Nothing is uploaded; it reads local files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

PLATFORM = "YouTube"
MIN_SAMPLES = 5
MIN_WORDS_FOR_SENTENCES = 25     # under this a draft cannot show sentence rhythm

STOP = set("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most
my myself no nor not now of off on once only or other our ours ourselves out over own same she should
so some such than that the their theirs them themselves then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you
your yours yourself yourselves im ive dont its thats youre cant wont isnt also get got one really
""".split())

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*|\d[\d,.]*")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
CONTRACTION_RE = re.compile(r"[A-Za-z]+'(?:t|re|s|ll|ve|d|m)\b", re.IGNORECASE)
I_WORDS = {"i", "me", "my", "mine", "myself", "i'm", "i've", "i'd", "i'll"}
WE_WORDS = {"we", "us", "our", "ours", "ourselves", "we're", "we've", "we'd", "we'll"}
YOU_WORDS = {"you", "your", "yours", "yourself", "you're", "you've", "you'd", "you'll"}
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿]")
NUM_RE = re.compile(r"(?<![A-Za-z])[$£€]?\d[\d,.]*%?")
CAPTION_TS = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3}\s*-->")

# Per-metric floor for the spread, so a profile where you never varied does
# not turn a tiny difference into a huge z-score.
FLOOR = {
    "sentence_len_mean": 3.0, "sentence_len_sd": 2.5, "contractions": 1.0, "i_rate": 1.0,
    "we_rate": 1.0, "you_rate": 1.0, "questions": 0.08, "exclamations": 0.05,
    "lowercase_starts": 0.15, "emoji": 0.5, "em_dashes": 0.5, "numbers": 1.0,
    "words": 15.0, "lines": 1.5,
}
LABEL = {
    "sentence_len_mean": "sentence length (words)", "sentence_len_sd": "sentence length spread",
    "contractions": "contractions /100w", "i_rate": "I /100w", "we_rate": "we /100w",
    "you_rate": "you /100w", "questions": "question share", "exclamations": "exclamation share",
    "lowercase_starts": "lower-case starts", "emoji": "emoji /100w", "em_dashes": "em dashes /1k chars",
    "numbers": "numbers /100w", "words": "words per sample", "lines": "lines per sample",
}
SENTENCE_METRICS = {"sentence_len_mean", "sentence_len_sd"}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return text.replace("’", "'").replace("‘", "'")


def strip_captions(raw: str) -> str:
    keep = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.isdigit() or s.upper().startswith("WEBVTT") or CAPTION_TS.match(s):
            continue
        keep.append(re.sub(r"<[^>]+>", "", s))
    return " ".join(keep)


def load_samples(paths: List[str]) -> List[str]:
    samples: List[str] = []
    for path in paths:
        with open(os.path.expanduser(path), encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        if path.lower().endswith((".srt", ".vtt")):
            text = strip_captions(raw)
            if text.strip():
                samples.append(text)
            continue
        for chunk in re.split(r"(?m)^\s*---\s*$", raw):
            if chunk.strip():
                samples.append(chunk.strip())
    return samples


def words(text: str) -> List[str]:
    return WORD_RE.findall(text)


def sentences(text: str) -> List[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s and words(s)]


def per100(n: float, total: int) -> float:
    return n * 100.0 / total if total else 0.0


def features(text: str) -> Dict[str, Any]:
    """Raw measurements for one piece of text. Never raises on empty input."""
    text = normalise(text)
    w = words(text)
    lw = [x.lower() for x in w]
    sents = sentences(text)
    lens = [len(words(s)) for s in sents]
    n_w = len(w)
    return {
        "words": n_w,
        "lines": len([ln for ln in text.splitlines() if ln.strip()]),
        "sentence_lengths": lens,
        "sentence_len_mean": statistics.mean(lens) if lens else 0.0,
        "sentence_len_sd": statistics.pstdev(lens) if len(lens) > 1 else 0.0,
        "contractions": per100(len(CONTRACTION_RE.findall(text)), n_w),
        "i_rate": per100(sum(1 for x in lw if x in I_WORDS), n_w),
        "we_rate": per100(sum(1 for x in lw if x in WE_WORDS), n_w),
        "you_rate": per100(sum(1 for x in lw if x in YOU_WORDS), n_w),
        "questions": (sum(1 for s in sents if s.endswith("?")) / len(sents)) if sents else 0.0,
        "exclamations": (sum(1 for s in sents if s.endswith("!")) / len(sents)) if sents else 0.0,
        "lowercase_starts": (sum(1 for s in sents if s[:1].islower()) / len(sents)) if sents else 0.0,
        "emoji": per100(len(EMOJI_RE.findall(text)), n_w),
        "em_dashes": text.count("—") * 1000.0 / len(text) if text else 0.0,
        "numbers": per100(len(NUM_RE.findall(text)), n_w),
        "lower_words": lw,
        "opener": " ".join(lw[:1]) if lw else "",
    }


METRICS = [k for k in LABEL]


def build_profile(samples: List[str]) -> Dict[str, Any]:
    if not samples:
        raise ValueError("no samples")
    feats = [features(s) for s in samples]
    metrics: Dict[str, Dict[str, float]] = {}
    for m in METRICS:
        vals = [f[m] for f in feats if m not in SENTENCE_METRICS or f["words"] >= 10]
        if not vals:
            vals = [f[m] for f in feats]
        metrics[m] = {"mean": round(statistics.mean(vals), 3),
                      "sd": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0}
    pooled = [n for f in feats for n in f["sentence_lengths"]]
    if pooled:
        metrics["sentence_len_mean"]["mean"] = round(statistics.mean(pooled), 3)
    doc_freq: Dict[str, int] = {}
    count: Dict[str, int] = {}
    for f in feats:
        for x in set(f["lower_words"]):
            if len(x) >= 3 and x not in STOP and not x[0].isdigit():
                doc_freq[x] = doc_freq.get(x, 0) + 1
        for x in f["lower_words"]:
            count[x] = count.get(x, 0) + 1
    signature = sorted((x for x, d in doc_freq.items() if d >= 2),
                       key=lambda x: (-doc_freq[x], -count[x], x))[:15]
    openers: Dict[str, int] = {}
    for f in feats:
        if f["opener"]:
            openers[f["opener"]] = openers.get(f["opener"], 0) + 1
    top_openers = [o for o, n in sorted(openers.items(), key=lambda kv: (-kv[1], kv[0])) if n >= 2][:5]
    return {
        "version": 1,
        "platform": PLATFORM,
        "samples": len(samples),
        "words": sum(f["words"] for f in feats),
        "metrics": metrics,
        "signature_words": signature,
        "openers": top_openers,
    }


def describe(profile: Dict[str, Any]) -> str:
    m = {k: v["mean"] for k, v in profile["metrics"].items()}
    sd = {k: v["sd"] for k, v in profile["metrics"].items()}
    person = max(("I", m["i_rate"]), ("we", m["we_rate"]), ("you", m["you_rate"]), key=lambda t: t[1])
    casing = ("mostly lower-case" if m["lowercase_starts"] > 0.6 else
              "mixed casing" if m["lowercase_starts"] > 0.25 else "normal sentence case")
    lines = [
        f"## Measured voice  (voice.py, {profile['samples']} samples, {profile['words']:,} words)",
        "",
        f"- **Sentence length:** {m['sentence_len_mean']:.1f} words on average, "
        f"spread {m['sentence_len_sd']:.1f} within a sample",
        f"- **Contractions:** {m['contractions']:.1f} per 100 words"
        + (" (uses them, keep them)" if m["contractions"] >= 1.5 else " (rarely, so drafts should not add them)"),
        f"- **Person:** I {m['i_rate']:.1f} / we {m['we_rate']:.1f} / you {m['you_rate']:.1f} per 100 words, "
        f"writes mostly as \"{person[0]}\"",
        f"- **Questions:** {m['questions'] * 100:.0f}% of sentences. **Exclamations:** {m['exclamations'] * 100:.0f}%",
        f"- **Casing:** {casing} ({m['lowercase_starts'] * 100:.0f}% of sentences start lower-case)",
        "- **Emoji:** " + ("none in any sample" if m["emoji"] == 0 else f"{m['emoji']:.1f} per 100 words"),
        "- **Em dashes:** " + ("none" if m["em_dashes"] == 0 else f"{m['em_dashes']:.1f} per 1,000 characters"),
        f"- **Numbers:** {m['numbers']:.1f} per 100 words",
        f"- **Length:** {m['words']:.0f} words (+/- {sd['words']:.0f}), {m['lines']:.1f} lines per sample",
    ]
    if profile["signature_words"]:
        lines.append("- **Words that are yours:** " + ", ".join(profile["signature_words"]))
    if profile["openers"]:
        lines.append("- **How you open:** " + ", ".join(f'"{o}"' for o in profile["openers"]))
    if profile["samples"] < MIN_SAMPLES:
        lines += ["", f"_Only {profile['samples']} sample(s). Add more for a profile worth trusting "
                      f"({MIN_SAMPLES}+ is the floor, 10+ is better)._"]
    return "\n".join(lines)


def check(profile: Dict[str, Any], draft: str) -> Dict[str, Any]:
    f = features(draft)
    rows = []
    hard: List[str] = []
    for m in METRICS:
        if m in SENTENCE_METRICS and f["words"] < MIN_WORDS_FOR_SENTENCES:
            rows.append({"metric": m, "label": LABEL[m], "draft": None, "profile": profile["metrics"][m]["mean"],
                         "z": None, "score": None})
            continue
        if m in ("words", "lines"):
            continue                       # length is a format choice, not voice
        mu = profile["metrics"][m]["mean"]
        sigma = max(profile["metrics"][m]["sd"], FLOOR[m])
        z = abs(f[m] - mu) / sigma
        score = max(0.0, min(100.0, 100.0 - max(0.0, z - 1.0) * 35.0))
        rows.append({"metric": m, "label": LABEL[m], "draft": round(f[m], 2), "profile": mu,
                     "z": round(z, 2), "score": round(score, 1)})
    pm = {k: v["mean"] for k, v in profile["metrics"].items()}
    if pm["emoji"] == 0 and f["emoji"] > 0:
        hard.append("emoji in the draft; none in any of your samples")
    if pm["em_dashes"] == 0 and f["em_dashes"] > 0:
        hard.append("em dash in the draft; you never use one. Run the humanizer")
    if pm["lowercase_starts"] > 0.6 and f["lowercase_starts"] < 0.25 and f["words"] >= 8:
        hard.append("sentence case in the draft; you write lower-case")
    if pm["contractions"] >= 2.0 and f["contractions"] == 0 and f["words"] >= MIN_WORDS_FOR_SENTENCES:
        hard.append("no contractions; you use them all the time")
    scored = [r["score"] for r in rows if r["score"] is not None]
    overall = round(statistics.mean(scored) * 0.7 + min(scored) * 0.3, 1) if scored else 0.0
    overall = max(0.0, overall - 10.0 * len(hard))
    verdict = "MATCH" if overall >= 75 and not hard else "CLOSE" if overall >= 60 else "DRIFT"
    return {"draft_words": f["words"], "rows": rows, "hard": hard, "score": overall, "verdict": verdict,
            "scored_on": len(scored)}


def render_check(res: Dict[str, Any], out=sys.stdout) -> None:
    print("\nVOICE CHECK", file=out)
    print("=" * 66, file=out)
    for r in res["rows"]:
        if r["score"] is None:
            print(f"  {r['label']:<26} {'n/a':>8}   (draft too short to show rhythm)", file=out)
            continue
        flag = "  <- off" if r["z"] > 2 else ""
        print(f"  {r['label']:<26} {r['draft']:>8.2f}   yours {r['profile']:>7.2f}   {r['score']:5.1f}{flag}",
              file=out)
    for h in res["hard"]:
        print(f"  HARD  {h}", file=out)
    print("-" * 66, file=out)
    print(f"  VOICE SCORE {res['score']:5.1f}   {res['verdict']}   (scored on {res['scored_on']} metrics)", file=out)
    if res["verdict"] != "MATCH":
        worst = [r for r in res["rows"] if r["score"] is not None]
        if worst:
            w = min(worst, key=lambda r: r["score"])
            print(f"  Furthest from you: {w['label']}. Fix that line first.", file=out)
    print("", file=out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Measure your voice from your own samples, then check drafts.")
    ap.add_argument("samples", nargs="*", help="text files of your own video transcripts, split on --- lines")
    ap.add_argument("--profile", help="a saved profile JSON instead of samples")
    ap.add_argument("--save", help="write the profile JSON here")
    ap.add_argument("--check", help="a draft to check against the profile")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.profile:
        try:
            with open(os.path.expanduser(args.profile), encoding="utf-8") as fh:
                profile = json.load(fh)
            if "metrics" not in profile or not all(m in profile["metrics"] for m in METRICS):
                raise ValueError("missing metrics")
        except (OSError, ValueError) as e:
            print(f"could not read profile {args.profile}: {e}", file=sys.stderr)
            return 2
    elif args.samples:
        try:
            samples = load_samples(args.samples)
        except OSError as e:
            print(f"could not read samples: {e}", file=sys.stderr)
            return 2
        if not samples:
            print("no text found in the samples", file=sys.stderr)
            return 2
        profile = build_profile(samples)
    else:
        ap.print_help(sys.stderr)
        return 2

    if args.save:
        path = os.path.expanduser(args.save)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2)

    if args.check:
        try:
            if args.check == "-":
                draft = sys.stdin.read()
            else:
                with open(os.path.expanduser(args.check), encoding="utf-8") as fh:
                    draft = fh.read()
        except OSError as e:
            print(f"could not read draft: {e}", file=sys.stderr)
            return 2
        if not draft.strip():
            print("the draft is empty", file=sys.stderr)
            return 2
        res = check(profile, draft)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            render_check(res)
        return 0 if res["verdict"] == "MATCH" else 1

    if args.json:
        print(json.dumps(profile, indent=2))
    else:
        print("\n" + describe(profile) + "\n")
        if args.save:
            print(f"profile saved to {args.save}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
