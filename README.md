# The YouTube agent skill

[![CI](https://github.com/gladosAagman/youtube-agent-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/gladosAagman/youtube-agent-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Fifteen Claude skills and two agents that run a YouTube channel. No signup, no API key, nothing to
connect.

One of them writes your script off 21 hook formulas and scores the hook before you waste a take on
it. One lints the title and the thumbnail as a single pairing, because writing them separately is
why half of your click surface says the same thing twice. One reads your audience-retention export
and tells you the exact second people left and what you were saying when they did. One turns a
transcript into an edit decision list. One finds the Shorts already hiding inside a long video. One
goes and finds what is working in your niche and ranks it by how far each video beat its own
channel, not by how big the channel is.

New in v2: a channel audit that reads your Studio export and names the ONE fix (packaging,
retention or topic) by comparing your recent uploads to your own history; an A/B test reader that
says whether a thumbnail test is decided or noise, which small channels need most; a sponsorship
rate card priced off your median views, not your best video; a voice profiler measured from your
own transcripts; calendar export for the plan; and one pre-publish check that runs everything.

**Nothing gets published until you do it.** These skills write. You upload.

## Install

**As a Claude Code plugin** (skills and agents together):

```
/plugin marketplace add gladosAagman/youtube-agent-skill
/plugin install youtube-agent@youtube-agent-skill
```

**Or copy the skill folders** into your Claude skills directory:

```bash
cp -r skills/yt-* ~/.claude/skills/
```

Project-local instead of global: copy the same folders into your repo's `.claude/skills/`. No Claude
Code at all? Paste any single `SKILL.md` at the top of a chat and it runs as a mode. You lose the
Python tools, which is most of the point of `/yt-script`, `/yt-retention`, `/yt-edit`, `/yt-audit`
and `/yt-test`, but the rest works.

Then spend ten minutes on [`templates/voice.md`](templates/voice.md). Copy it to
`~/.claude/youtube/voice.md` and fill it in, or send Claude three of your own videos and say "write
my voice.md from these". Every skill reads that file. It matters more here than anywhere else,
because you have to say the words out loud. Better: run `/yt-voice` on three of your own caption
files and it fills the file from what you actually said.

## The fifteen

| command | what it does |
| --- | --- |
| `/yt-script` | One idea into a script. Five hooks off [21 formulas](skills/yt-script/hooks.json), scored, then the spoken script with the retention beats marked. |
| `/yt-package` | Title and thumbnail as one pairing, linted for truncation, duplication and vagueness. |
| `/yt-edit` | A transcript into an edit decision list: dead air, filler cues, retakes, with timecodes. |
| `/yt-comment` | The comment section triaged into four piles, then replies in your voice. Says which one to pin. |
| `/yt-plan` | A week that fits the hours you actually have. One anchor, one cheap one, three Shorts. |
| `/yt-viral` | What is working in your niche, ranked by multiple over each channel's own median. |
| `/yt-retention` | Your retention export read properly: hook leak, the cliffs, the slide, and what to change. |
| `/yt-shorts` | The Shorts already inside a long video, with a new first line written for each. |
| `/yt-seo` | The description, the tags that are worth having, and the three queries this should win. |
| `/yt-chapters` | Chapters from a transcript, validated against YouTube's own rules so they render. |
| `/yt-audit` | The whole channel, ending in ONE fix rather than twenty. **v2:** `channel.py` reads your Studio export and names it. |
| `/yt-test` | **New.** Thumbnail and title A/B tests: design them, then say WINNER, NOT YET or NO CALL with a real significance test. |
| `/yt-sponsor` | **New.** A rate card from your median views, the pitch, the reply to an inbound offer, the terms that move the price, and the read placed where it does not wreck retention. |
| `/yt-voice` | **New.** Measures how you talk from your own transcripts and flags a script that drifted from it. |
| `/yt-preflight` | **New.** Package, hook, runtime, search queries, chapter validity and voice, one READY or FIX FIRST. |

## The two agents

| agent | what it does |
| --- | --- |
| `yt-producer` | One idea (or one finished transcript) to an upload-ready package: script, title and thumbnail, description, chapters, Shorts, pre-flight. |
| `yt-analyst` | Your exports to ONE diagnosis and ONE fix: the channel audit, retention for the worst videos, test results read honestly. |

## The eleven tools

Every one of these runs on a clean Python 3 with no dependencies. They are the reason the skills are
not just prompts. The first six shipped in v1; the last five are new.

```bash
python3 skills/yt-script/hookscore.py --hook "one line"        # 5-property hook panel
python3 skills/yt-package/title.py --title "..." --thumb "..." # title + thumbnail linter
python3 skills/yt-edit/deadair.py transcript.srt               # edit decision list
python3 skills/yt-chapters/chapters.py transcript.srt          # validated chapters
python3 skills/yt-retention/retention.py retention.csv         # where they left, and why
python3 skills/yt-viral/swipe.py collected.json --min 2.0      # outliers by own-channel multiple
python3 skills/yt-audit/channel.py "Table data.csv"            # the ONE fix, from your Studio export
python3 skills/yt-test/abtest.py --variant A:12400:496 --variant B:11900:571   # decided, or noise?
python3 skills/yt-sponsor/ratecard.py --views ... --cpm-low 20 --cpm-high 35  # rate from median views
python3 skills/yt-voice/voice.py v1.srt v2.srt v3.srt --save ~/.claude/youtube/voice.json
python3 skills/yt-plan/plan2ics.py ~/.claude/youtube/plan.md -o week.ics
python3 skills/yt-preflight/preflight.py --title "..." --thumb "..." --script s.txt --description d.txt
```

### The one fix, from your own export

`channel.py` judges every long-form video against this channel's own medians (views, CTR, average
percentage viewed), puts each recent upload in a quadrant, and names the one that holds most of
them. Shorts are left out by default because they bend every median. From a synthetic test file:

```
  THE ONE FIX
    RETENTION  (WORKING 4, RETENTION 3, PACKAGING 2, TOPIC 1 across the last 10)
    People click and leave. The packaging is fine; the first 30 seconds are not delivering what it
    promised. Export retention for the worst two and run /yt-retention.
```

### Is the test decided?

A thumbnail test on a small channel is usually decided by noise and then believed. `abtest.py`
runs a two-proportion z-test of each challenger against the control, splits the significance bar
across challengers, and refuses to call a winner under 1,000 impressions an arm:

```
  TEST  ·  control A: 9 clicks / 300 impressions = 3.00% CTR
  alpha 0.05 split across 2 challenger(s) -> 0.0250 each

    B           10.00% CTR   +233.3% vs control   p=0.0005   NOT YET
               looks real, but an arm is under 1,000 impressions. Let it run.
    C            3.33% CTR    +11.1% vs control   p=0.8157   NOT YET
               about 52,462 impressions per arm to call this gap (52,162 more)
```

Studio's own Test & Compare judges on watch time share and shows percentages without counts, so
this tool does not pretend to test those.

### A rate from the typical video

`ratecard.py` prices off the median of your recent long-form views and shows the 25th-75th
percentile as the range a sponsor should expect. There is no default CPM: you give it the range
from real quotes, because a number from a blog post is not yours.

```
    median views            26,300   (what a sponsor should expect)
    typical range           20,475 - 38,275   (25th to 75th percentile)
    average                 65,233   2.48x the median. One or two hits are inflating it. Do not quote off this.

    at $20-$35 CPM
    integration, flat   $526 - $920
```

### Everything before publish

`preflight.py` runs the title and thumbnail lint, the hook score on the script's first sentence,
the runtime, the `/yt-seo` query test against the title and first two description lines, and
YouTube's chapter rules on the description's timestamps, which is the check that catches a block
that would silently not render:

```
    PACKAGE   PASS  100/100, 39 chars
    HOOK      WARN  60 WORKABLE · The Statistic
    RUNTIME   PASS  1,238 words, about 8:15 at 150 wpm
    QUERIES   WARN  1/2 queries covered by the title + first 2 lines
    CHAPTERS  FAIL  3 timestamps, will not render
```

## The fine print

The part most packs leave out.

**It does not publish.** YouTube's Data API would allow it with your own OAuth, which makes this
pack different from the LinkedIn and Instagram ones, where posting is not available at all. It is
still not built here: every skill ends in a block you copy and a question — ship it, or change it?
Anything that claims to run your channel unattended should be read with that distinction in mind.

**`hookscore.py` is a heuristic, not a predictor.** The panel was built and calibrated against 74
real short-form hooks (the first 15 seconds of auto-captions, top-8 and bottom-8 by views across
five channels). It separates deliberately bad hooks from real ones well. It separates a given
creator's hits from their own misses barely at all. A low score is a reason to look again; a high
score is not a promise.

**The formula classifier is about the words, not the result.** When `/yt-viral` says a title used
The Statistic, that is a judgement about the title you can see, not a claim about why the video got
its views.

**`/yt-viral` reads, it does not scrape.** Public listings only. It never logs in as you and never
touches your credentials.

**Tags barely matter** and this pack says so instead of selling you a tag generator.

**Nothing invents a number.** If a skill wants a figure it does not have, it asks you for it or
writes the line without it.

## Files

```
skills/yt-script/hooks.json          21 hook formulas with classifier patterns
skills/yt-script/hookscore.py        five-property hook panel
skills/yt-package/title.py           title + thumbnail pairing linter
skills/yt-edit/deadair.py            transcript -> edit decision list
skills/yt-chapters/chapters.py       transcript -> validated chapters
skills/yt-retention/retention.py     retention export -> hook leak, cliffs, slide
skills/yt-viral/swipe.py             outliers by own-channel multiple
skills/yt-audit/channel.py           Studio export -> quadrants and the ONE fix          v2
skills/yt-test/abtest.py             A/B test significance and sample size               v2
skills/yt-sponsor/ratecard.py        sponsorship rate from median views                  v2
skills/yt-voice/voice.py             voice profile from your transcripts, drift check    v2
skills/yt-plan/plan2ics.py           the plan as calendar reminders (.ics)               v2
skills/yt-preflight/preflight.py     every pre-publish check, one verdict                v2
agents/yt-producer.md                idea or transcript -> upload-ready package          v2
agents/yt-analyst.md                 exports -> one diagnosis, one fix                   v2
scripts/validate.py                  structural checks, run in CI                        v2
tests/                               regression tests for v1, unit tests for v2          v2
templates/voice.md                   your voice profile. Fill this in first.
```

Your own files live in `~/.claude/youtube/`: `voice.md`, `voice.json` and `plan.md`.

## Development

```bash
python3 scripts/validate.py              # skills, agents, manifests, JSON, README coverage
python3 -m unittest discover -s tests    # no network
```

CI runs both on Linux, macOS and Windows. See [CONTRIBUTING.md](CONTRIBUTING.md) for the rules a pull
request has to keep and [CHANGELOG.md](CHANGELOG.md) for what changed.

## License

[MIT](LICENSE).
