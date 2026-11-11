# Contributing

Thanks for helping. This pack has a few rules that are the point of it, so
read these before opening a pull request.

## The rules that are not negotiable

1. **Nothing posts.** No skill, tool or agent publishes, replies, likes,
   follows, messages or uploads on YouTube, and none drives a browser to do it.
   Every output ends in text the user copies. Pull requests that add posting
   or automation will be closed, however they are framed.
2. **Nothing scrapes.** Tools read files the user exported, or URLs the user
   picked through a documented public endpoint, at human scale.
3. **Nothing fabricates.** No invented metrics, clients, results or sources.
   A missing number becomes `{{your number}}` and a flag.
4. **Claims carry their sample size.** If a tool reports a pattern, it prints
   the n and a confidence word, and says when there is too little data.
5. **Standard library only.** Every tool runs on a clean Python 3.10+ with no
   `pip install`. That is what lets a skill folder be copied anywhere.

## Layout

```
skills/<name>/SKILL.md    the skill: frontmatter (name = folder, description) and instructions
skills/<name>/*.py        tools the skill runs. Import siblings via ../<other-skill>/ paths.
skills/<name>/*.json      data the tools read (formulas, lexicons, rubrics)
agents/<name>.md          subagents that orchestrate several skills
templates/                files the user copies and fills in
scripts/validate.py       structural checks (run in CI)
tests/                    unittest suites (run in CI)
```

## Before you open a pull request

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests
```

Both must pass. New tools need tests for normal input **and** for the edge
cases: empty input, malformed rows, boundaries, and anything that ends up in
HTML, CSV or a calendar file (escape it). New skills need a README row.

## Style

Match the existing voice: short sentences, the reason before the rule, and
an honest note on what a tool cannot tell you. Keep exit codes consistent:
0 for a clean result, 1 for "needs fixing", 2 for bad input.
