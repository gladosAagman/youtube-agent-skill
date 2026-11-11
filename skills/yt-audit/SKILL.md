---
name: yt-audit
description: >-
  Audit a YouTube channel end to end - packaging, consistency, the first
  fifteen seconds, and what to fix first. Use for "audit my channel", "why
  isn't my channel growing", "review my videos", or a pasted channel URL.
---

# yt-audit

An audit that lists twenty problems is a way of avoiding the one that matters. This ends in ONE fix.

## Before you write

1. Read `~/.claude/youtube/voice.md` if it exists. That is the user's voice profile: how they talk
   on camera, the words they never use, who they are talking to, what they will not claim. If it
   does not exist, ask for **three of their own videos**, read or transcribe them, infer the voice,
   and write the file. A script in the wrong voice is worse than no script, because they have to
   read it out loud.
2. Never invent a number, a result or a source. If a figure would strengthen it and you do not have
   one, ask for it or write the line without it.

## What to look at, in this order

1. **The last ten titles, as a set.** Read them as a list, the way the channel page shows them. Do
   they promise different things? Run them through `../yt-package/title.py`. A channel where every
   title is the same shape has a format problem, not a title problem.
2. **The thumbnails, at feed size.** Shrink them. What survives? If three of them are unreadable at
   that size, that is the fix and nothing else matters yet.
3. **The first fifteen seconds of the three most recent.** Transcribe them and score with
   `../yt-script/hookscore.py`. This is where most channels lose.
4. **Upload rhythm.** Not frequency - CONSISTENCY. Six videos in one week and then nothing for a
   month is worse than one a fortnight forever.
5. **The retention shape**, if they can export it. `/yt-retention`.

## What to hand back

- The single biggest fix, named, with what to do this week.
- Three things that are already working, so they do not break them. Be specific; "your energy is
  good" is not an observation.
- What NOT to do yet, and why.

Never open an audit with praise you do not mean, and never end one with a list of twenty things.

## The tool (v2)

`channel.py` in this folder does steps 1, 4 and 5's arithmetic on the Studio
export, and ends in ONE fix the way this skill does:

```bash
python3 channel.py "Table data.csv"            # Advanced mode -> Content -> download CSV
python3 channel.py "Table data.csv" --last 20
```

Every video is judged against this channel's own medians: views as a
multiple of the median, CTR and average percentage viewed against the
channel's median CTR and APV. Each recent video lands in a quadrant
(WORKING, PACKAGING, RETENTION, TOPIC) and the fix is the problem quadrant
holding most of them. The medians come from the whole export and the fix
from how the last ten compare to them, so export at least 30 videos: the
question is how recent uploads are drifting against the channel's own
history. Shorts are left out unless `--include-shorts`, because they bend
every median. Then do the parts it cannot: the thumbnails at feed
size and the first fifteen seconds.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**
