#!/usr/bin/env python3
"""
validate.py - structural checks for this plugin, run in CI and before every commit.

  - .claude-plugin/plugin.json and marketplace.json parse and carry the required fields
  - every skills/<name>/SKILL.md has frontmatter whose name matches its folder and a
    description that fits Claude's 1,024-character limit
  - every agents/<name>.md has a name matching its file and a description
  - every .json file in the repo parses
  - every .py file compiles
  - the README mentions every skill and every agent, so docs cannot drift silently

Exit 0 when clean, 1 with a list of problems otherwise. Standard library only.

    python3 scripts/validate.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_DESCRIPTION = 1024
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


def frontmatter(path: str) -> Tuple[Optional[Dict[str, str]], str]:
    """A small YAML-subset reader: key: value and key: >- folded blocks.
    Enough for skill and agent frontmatter, with no dependency."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    out: Dict[str, str] = {}
    key: Optional[str] = None
    folded: List[str] = []
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km and not line.startswith(" "):
            if key and folded:
                out[key] = " ".join(folded).strip()
            key, val = km.group(1), km.group(2).strip()
            folded = []
            if val in (">-", ">", "|", "|-"):
                continue
            out[key] = val.strip("\"'")
            key = None
        elif key is not None:
            folded.append(line.strip())
    if key and folded:
        out[key] = " ".join(folded).strip()
    return out, text[m.end():]


def walk(ext: str) -> List[str]:
    found = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        found += [os.path.join(d, f) for f in files if f.endswith(ext)]
    return sorted(found)


def rel(p: str) -> str:
    return os.path.relpath(p, ROOT)


def main() -> int:
    problems: List[str] = []

    plugin_path = os.path.join(ROOT, ".claude-plugin", "plugin.json")
    market_path = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    try:
        with open(plugin_path, encoding="utf-8") as fh:
            plugin = json.load(fh)
        for k in ("name", "description", "version"):
            if not plugin.get(k):
                problems.append(f"plugin.json: missing {k}")
        if plugin.get("version") and not re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"]):
            problems.append("plugin.json: version is not semver")
    except (OSError, ValueError) as e:
        problems.append(f"plugin.json: {e}")
        plugin = {}
    try:
        with open(market_path, encoding="utf-8") as fh:
            market = json.load(fh)
        if not market.get("name") or not market.get("owner", {}).get("name"):
            problems.append("marketplace.json: needs name and owner.name")
        names = [p.get("name") for p in market.get("plugins", [])]
        if plugin.get("name") and plugin["name"] not in names:
            problems.append(f"marketplace.json: does not list plugin {plugin.get('name')!r}")
    except (OSError, ValueError) as e:
        problems.append(f"marketplace.json: {e}")

    skills_dir = os.path.join(ROOT, "skills")
    skills = sorted(d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d)))
    for s in skills:
        p = os.path.join(skills_dir, s, "SKILL.md")
        if not os.path.exists(p):
            problems.append(f"skills/{s}: no SKILL.md")
            continue
        fm, body = frontmatter(p)
        if fm is None:
            problems.append(f"skills/{s}/SKILL.md: no frontmatter")
            continue
        if fm.get("name") != s:
            problems.append(f"skills/{s}/SKILL.md: name {fm.get('name')!r} does not match the folder")
        if not NAME_RE.match(fm.get("name", "")):
            problems.append(f"skills/{s}/SKILL.md: name must be lower-case letters, digits and hyphens")
        desc = fm.get("description", "")
        if not desc:
            problems.append(f"skills/{s}/SKILL.md: empty description")
        elif len(desc) > MAX_DESCRIPTION:
            problems.append(f"skills/{s}/SKILL.md: description is {len(desc)} characters (max {MAX_DESCRIPTION})")
        if len(body.strip()) < 200:
            problems.append(f"skills/{s}/SKILL.md: body is nearly empty")
        for ref in re.findall(r"`(?:\.\./)?([\w-]+/[\w-]+\.(?:py|json))`", body):
            if not os.path.exists(os.path.join(skills_dir, ref)):
                problems.append(f"skills/{s}/SKILL.md: refers to {ref}, which does not exist")

    agents: List[str] = []
    agents_dir = os.path.join(ROOT, "agents")
    if os.path.isdir(agents_dir):
        for f in sorted(os.listdir(agents_dir)):
            if not f.endswith(".md"):
                continue
            name = f[:-3]
            agents.append(name)
            fm, _ = frontmatter(os.path.join(agents_dir, f))
            if fm is None or fm.get("name") != name or not fm.get("description"):
                problems.append(f"agents/{f}: needs frontmatter with name {name!r} and a description")

    for p in walk(".json"):
        try:
            with open(p, encoding="utf-8") as fh:
                json.load(fh)
        except ValueError as e:
            problems.append(f"{rel(p)}: invalid JSON: {e}")

    for p in walk(".py"):
        try:
            with open(p, encoding="utf-8") as fh:
                compile(fh.read(), p, "exec")          # in memory: no .pyc written anywhere
        except SyntaxError as e:
            problems.append(f"{rel(p)}: does not compile: line {e.lineno}: {e.msg}")

    readme = os.path.join(ROOT, "README.md")
    with open(readme, encoding="utf-8") as fh:
        text = fh.read()
    for s in skills:
        if f"/{s}`" not in text and f"/{s} " not in text:
            problems.append(f"README.md: skill /{s} is not documented")
    for a in agents:
        if a not in text:
            problems.append(f"README.md: agent {a} is not documented")
    if not os.path.exists(os.path.join(ROOT, "LICENSE")):
        problems.append("LICENSE is missing")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        print("")
        return 1
    print(f"ok  ·  {len(skills)} skills, {len(agents)} agents, {len(walk('.py'))} Python files, "
          f"{len(walk('.json'))} JSON files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
