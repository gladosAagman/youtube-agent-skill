---
name: yt-preflight
description: >-
  Run every pre-publish check on a YouTube upload in one pass - the title and
  thumbnail as a pairing, the script's opening hook, runtime, whether the
  title and first description lines contain the searches the video should
  win, whether the chapter timestamps will actually render, and drift from
  the creator's measured voice. Use for "check before I publish", "is this
  ready to upload", "preflight", "final check", or right after /yt-package
  and /yt-seo.
---

# yt-preflight

Six checks live in five different skills, and the one that gets skipped is the
chapters block that silently does not render. This runs all of them.

```bash
python3 preflight.py --title "I Tested 7 Thumbnail Styles for 30 Days" --thumb "ONE WON" \
    --script script.txt --description description.txt --queries "thumbnail test;youtube ctr"
```

Only `--title` is required. Each other flag adds its checks.

| stage | from | fails when |
| --- | --- | --- |
| PACKAGE | `../yt-package/title.py` | the pairing scores under 60 |
| HOOK | `../yt-script/hookscore.py` | the script's first sentence scores WEAK |
| RUNTIME | 150 words a minute | never; it is information |
| QUERIES | `/yt-seo`'s query test | warns when a query's words are missing from the title and first two description lines |
| CHAPTERS | YouTube's rules | the timestamps break 0:00-first, 3+, or 10s-minimum, so they will not render |
| VOICE | `../yt-voice/voice.py` | the script drifted (only when `~/.claude/youtube/voice.json` exists) |

## Order of operations

1. `/yt-script`, `/yt-package`, `/yt-seo`, `/yt-chapters` as normal.
2. `preflight.py` with everything.
3. FIX FIRST: fix item 1, run it again. READY: hand over the title,
   thumbnail text, description and chapters as copy-ready blocks, then the
   table.

## What READY does not mean

Nothing checkable is wrong. It is not a view prediction: `hookscore.py` and
`title.py` are lints, and the README says how well the hook panel does and
does not separate hits from misses.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends
in a block the user copies, and the last line of every run is the question:
**ship it, or change it?**
