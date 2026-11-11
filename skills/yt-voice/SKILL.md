---
name: yt-voice
description: >-
  Measure how the creator actually talks on camera from their own transcripts
  and write voice.md from evidence, then check any script for drift before
  they read it out loud. Use for "write my voice.md", "learn how I talk",
  "this script doesn't sound like me", "make it sound like me", first-time
  setup of the pack, or when the user shares transcripts or caption files of
  their own videos.
---

# yt-voice

On YouTube the creator has to say the words. A script in the wrong voice is
not just off-brand, it is unreadable on camera: the sentences are the wrong
length for their breath, the words are not theirs, and it shows in the take.
This measures the voice from what they have already said.

```bash
python3 voice.py video1.srt video2.srt video3.srt               # caption files: one sample each
python3 voice.py transcripts.txt --save ~/.claude/youtube/voice.json   # text: --- between samples
python3 voice.py --profile ~/.claude/youtube/voice.json --check script.txt
```

## Input

Three to ten transcripts of the creator's own videos: `.srt` or `.vtt`
caption files (timestamps are stripped automatically, each file is one
sample), or plain text with a `---` line between transcripts. Use their
best-performing videos and their most recent ones, not an old style they
have moved away from.

**Auto-captions have no punctuation**, which makes sentence-length numbers
meaningless. Use the creator's edited captions, a Whisper transcript, or
the transcript YouTube generates after they have corrected it. Say this if
the profile shows one 300-word "sentence".

## What it measures

Sentence length and spread (how long they talk before a breath), contractions,
I / we / you (does the channel talk *to* someone), questions, numbers per 100
words, the words that recur across videos, and how videos open. Each is a
mean and a spread.

## Then write voice.md

1. Measure and save the profile.
2. Fill in `templates/voice.md`: who they are talking to, what they will not
   claim, their format.
3. Paste the **Measured voice** block under "How I actually talk". Point out
   where it disagrees with what the creator said about themselves.
4. Save to `~/.claude/youtube/voice.md`.

## Checking a script

`--check script.txt` scores the script against the profile and names the
metric furthest from them. `/yt-preflight` runs it automatically when the
profile exists. A script that scores DRIFT gets read out loud once before
anyone fixes it: the ear finds the wrong line faster than the numbers.

## Say this honestly

Stylometry on a few transcripts. It catches a script that drifted into
generic YouTube voice. It does not make a script good, and it is for the
creator's own voice only.
