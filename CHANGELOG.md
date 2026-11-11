# Changelog

## [2.0.0] - 2026-11-09

### Added
- `channel.py` in `/yt-audit`: reads the Studio content export, judges every
  long-form video against the channel's own medians, sorts recent uploads
  into WORKING / PACKAGING / RETENTION / TOPIC and names the one fix. Shorts
  are excluded by default.
- `/yt-test` with `abtest.py`: two-proportion significance for thumbnail and
  title tests, Bonferroni across challengers, a 1,000-impression floor, and
  the sample still needed. Says plainly that Studio's Test & Compare judges on
  watch time and cannot be re-tested from percentages.
- `/yt-sponsor` with `ratecard.py`: a rate from median views with no default
  CPM, the terms that move the price, pitch and reply, and read placement.
- `/yt-voice` with `voice.py` (reads .srt / .vtt directly) and
  `/yt-preflight` with `preflight.py` (package, hook, runtime, query test,
  chapter validity, voice).
- `plan2ics.py` in `/yt-plan`.
- Agents: `yt-producer` and `yt-analyst`.
- v2 sections in `/yt-audit`, `/yt-package`, `/yt-plan`, `/yt-seo`,
  `/yt-chapters`, `/yt-script` and `/yt-retention`, each placed before the
  skill's gate.

### Fixed
- `deadair.py`, `title.py`, `hookscore.py` and `swipe.py` now close the files
  they open and read them as UTF-8, so emoji in a transcript or title list no
  longer fail on systems whose default encoding is not UTF-8. Output is
  unchanged.

### Infrastructure
- `scripts/validate.py`: checks the plugin manifests, every skill's and agent's
  frontmatter, every JSON and Python file, and that the README documents every
  skill and agent.
- `tests/`: regression tests that pin the v1 tools' documented behaviour, and
  unit tests for every v2 tool covering normal input and edge cases (empty
  input, malformed rows, boundaries, injection).
- GitHub Actions CI on Linux, macOS and Windows, Python 3.10 and 3.13.
- Installable as a Claude Code plugin: `marketplace.json` gained the `owner`
  field and `plugin.json` gained author, repository, homepage and license.
- MIT license, CONTRIBUTING.md, SECURITY.md.

### Preserved
Every v1 skill, tool, data file and template is unchanged in behaviour. The
first commit in this repository is v1 exactly as it was; every v2 change to
an existing skill is an added section marked "(v2)".

## [1.0.0]

The original eleven skills.
