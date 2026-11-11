---
name: yt-test
description: >-
  Design and read a thumbnail or title A/B test properly - what to vary,
  how long to run it, and whether the result is a real winner or noise,
  using a two-proportion significance test on impressions and clicks. Use
  for "A/B test my thumbnail", "test and compare", "which thumbnail won",
  "is this result real", "should I swap the thumbnail", or a pasted test
  result.
---

# yt-test

A thumbnail test on a small channel is usually decided by noise, then
believed. 40 clicks against 52 feels like a winner. It is not one. This
says whether it is.

```bash
python3 abtest.py --variant A:12400:496 --variant B:11900:571        # control first
python3 abtest.py results.csv                                         # name,impressions,clicks
```

## Before you write

1. Read `~/.claude/youtube/voice.md` if it exists. Variant titles still have
   to sound like the channel.
2. Never invent a number. If the user has percentages and no counts, say what
   that can and cannot tell you (below).

## Designing the test

- **Change one thing.** The face, or the text, or the colour. Two changes at
  once and the result cannot say which one did it.
- **Make the variants genuinely different.** Two near-identical thumbnails
  produce a test that cannot be called at any sample.
- **Write them with `/yt-package`**, and lint each with `title.py --thumb`.
- **Decide the stop rule first:** the impressions per arm, or a date. Stopping
  when it looks good is how noise becomes a winner.

## Reading the result

| verdict | means |
| --- | --- |
| **WINNER** | unlikely to be noise, and both arms have 1,000+ impressions |
| **LOSER** | the challenger is reliably worse than the control |
| **NOT YET** | the gap might be real; the tool says roughly how many more impressions it needs |
| **NO CALL** | too close to call at any realistic sample. Keep the one that fits the video better |

With three variants, the significance bar is split between them, so a
three-way test is not three chances to fool yourself.

## YouTube's own Test & Compare

Studio picks its winner on **watch time share**, not click-through, and it
shows percentages without the counts behind them. A percentage alone cannot
be tested for significance, so `abtest.py` does not try. Use Studio's
verdict for Studio's test, and say "Studio judged this on watch time".

## CTR is the click, not the watch

A thumbnail that wins on CTR and loses average view duration over-promised.
Check both windows before keeping the winner, and if the video's retention
dropped, the fix is the opening, not another thumbnail: `/yt-retention`.

## The gate

Nothing here publishes or swaps anything. This skill reads and you decide.
The last line of every run is the question: **ship it, or change it?**
