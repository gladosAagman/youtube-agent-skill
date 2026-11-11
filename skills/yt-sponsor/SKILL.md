---
name: yt-sponsor
description: >-
  Run YouTube sponsorships without underpricing or overpromising - a rate
  card from the channel's real median views, the pitch to a brand, the
  reply to an inbound offer, the contract terms to ask about, and a sponsor
  read placed where it does not wreck retention. Use for "how much should I
  charge", "rate card", "a brand reached out", "sponsorship", "pitch a
  sponsor", "write the ad read", "is this deal fair".
---

# yt-sponsor

Most creators underprice the first deal and overpromise on views, and both
come from quoting off their best video. This prices off the typical one, and
it writes the read so the sponsor slot does not become the retention cliff.

```bash
python3 ratecard.py --views 41000 18000 22500 30100 19800 26000 --cpm-low 20 --cpm-high 35
python3 ratecard.py --views-file last10.txt --cpm-low 15 --cpm-high 30
```

## Before you write

1. Read `~/.claude/youtube/voice.md` if it exists. A sponsor read in the wrong
   voice is the most skipped 60 seconds in the video.
2. Never invent a number. Not views, not audience demographics, not past
   results for other sponsors. Ask for them or leave them out.

## The rate

- **Views:** the last ten long-form videos, from Studio. Not the channel
  average, which one hit inflates. `ratecard.py` uses the median and prints
  the 25th-75th percentile as the range a sponsor should expect.
- **CPM: the user supplies it.** From quotes they have received, a creator in
  their niche who shared rates, or the brand's own offer. The tool has no
  default on purpose: niche, audience country and placement move it several
  times over, and a number from a blog post is not theirs.
- **Shorts** are priced separately, if at all. Their views do not translate.

## The terms that move the price

Ask about each one before agreeing to a number:

| term | why it matters |
| --- | --- |
| **Usage rights** | the brand running the read as an ad elsewhere is a separate fee |
| **Exclusivity** | no competitors for N days costs the creator other deals |
| **Whitelisting / ads from the channel** | the brand spending from the creator's account |
| **Revisions** | how many rounds, and who approves the script |
| **Deliverables** | integration length, placement, pinned comment, description link |
| **Payment terms** | net 30 is normal; net 90 is a loan. Ask for part up front on a first deal |
| **Reporting** | what they need back and when, so nobody argues about views later |

## The pitch (outbound)

Three short paragraphs: why this brand and this audience (specific, from the
channel's real comments or analytics), the offer (format, timing, median
views, the rate range), one ask. Attach nothing the user cannot back up.

## The reply (inbound)

Thank them, ask the questions in the table above that the offer left out,
and give the rate range. Never accept the first number in the first reply.

## The read

- **Placement:** after the hook has paid off, not inside the first 60
  seconds. `/yt-retention` on past sponsored videos shows where the drop was.
- **Length:** 45-75 seconds for an integration. Longer is a cliff.
- **Shape:** a transition line that belongs to the video, the creator's real
  use of the product, one specific benefit, the offer, the return line.
- **Disclosure:** say it is sponsored, out loud, near the start of the read,
  and tick "includes paid promotion" in Studio. That is YouTube's rule, and
  advertising regulators in most countries require disclosure too.

Run the read through `/yt-script`'s hook scorer for the transition line and
`/yt-preflight --script` for voice.

## The gate

Nothing here publishes, sends or signs anything. This skill writes and you
send. Every output ends in a block the user copies, and the last line of
every run is the question: **ship it, or change it?**
