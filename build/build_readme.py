#!/usr/bin/env python3
"""Rewrite the live regions of README.md, then regenerate the graphics.

Two regions are owned by this script, each delimited by a matched pair of HTML
comments so the rest of the file is never touched:

    <!-- dateline:start -->  ... <!-- dateline:end -->
    <!-- upstream:start -->  ... <!-- upstream:end -->

The merged-PR counts come from the GitHub Search API, which returns a
`total_count` for a query -- so one request per repository answers the question
with no pagination at all.

Safety rail: if the API fails, rate-limits, or answers 0 where we previously had
a positive number, we keep the previous number and say so on stderr. A profile
that silently claims 0 merged PRs because of an HTTP 403 is worse than a stale one.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

USER = "manavmax"
EPOCH = dt.date(2026, 2, 3)          # NO. 001 -- first issue of this masthead
ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

#            repo                          display        maintainer          where I worked
UPSTREAM = [
    ("google-gemini/gemini-cli",   "Gemini CLI",   "Google",
     "`cli` `core` `extensions` `devtools`"),
    ("oppia/oppia",                "Oppia",        "Oppia Foundation",
     "LEAP team — led a Redis infrastructure upgrade"),
    ("open-metadata/OpenMetadata", "OpenMetadata", "Collate",
     "metadata platform"),
]


def gh(path: str) -> dict:
    """One authenticated GET against the GitHub REST API."""
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"{USER}-profile-builder",
            **({"Authorization": f"Bearer {t}"} if (t := os.environ.get("GH_TOKEN")) else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def merged_prs(repo: str) -> int | None:
    """Merged PRs authored by USER in `repo`, or None if the API did not answer."""
    q = urllib.parse.quote_plus(f"repo:{repo} type:pr author:{USER} is:merged")
    try:
        return int(gh(f"/search/issues?q={q}&per_page=1")["total_count"])
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError,
            TimeoutError, json.JSONDecodeError) as e:
        print(f"  ! {repo}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def region(md: str, key: str) -> tuple[int, int]:
    """Character span *between* the `key:start` and `key:end` sentinels."""
    m = re.search(
        rf"<!--\s*{re.escape(key)}:start\s*-->(.*?)<!--\s*{re.escape(key)}:end\s*-->",
        md, re.S)
    if not m:
        raise SystemExit(f"README.md is missing the '{key}' sentinel pair")
    return m.start(1), m.end(1)


def replace(md: str, key: str, body: str) -> str:
    a, b = region(md, key)
    return md[:a] + body + md[b:]


def main() -> int:
    md = README.read_text(encoding="utf-8")
    today = dt.date.today()

    # --- previous counts, parsed back out of the markers we ourselves wrote ---
    prior = {r: int(n) for r, n in re.findall(r"<!--\s*n:(\S+)=(\d+)\s*-->", md)}

    print("counting merged pull requests upstream")
    counts, degraded = {}, []
    for repo, *_ in UPSTREAM:
        n = merged_prs(repo)
        if n is None or (n == 0 and prior.get(repo, 0) > 0):
            n = prior.get(repo, 0)
            degraded.append(repo)
        counts[repo] = n
        print(f"  {repo:32s} {n:3d}{'  (kept previous)' if repo in degraded else ''}")

    total = sum(counts.values())
    if degraded:
        print(f"  ! degraded: kept previous counts for {', '.join(degraded)}", file=sys.stderr)

    # --- region 1: the upstream table -------------------------------------
    rows = [
        "",
        "| Project | Maintained by | Where I worked | Merged |",
        "|:--|:--|:--|--:|",
        *(f"| **[{name}](https://github.com/{repo})** <!-- n:{repo}={counts[repo]} --> "
          f"| {who} | {where} | `{counts[repo]}` |"
          for repo, name, who, where in UPSTREAM),
        "",
        f"<samp><b>{total}</b> pull requests merged by maintainers who owe me nothing · "
        f"counted by the GitHub Search API on <code>{today:%Y-%m-%d}</code>, not by me</samp>",
    ]
    md = replace(md, "upstream", "\n".join(rows) + "\n")

    # --- region 2: the dateline -------------------------------------------
    issue = (today - EPOCH).days + 1
    md = replace(md, "dateline",
                 f"`VOL. I` · `NO. {issue:03d}` · `{today:%d %B %Y}`".upper()
                 + " · `BUILT BY GITHUB ACTIONS`")

    README.write_text(md, encoding="utf-8")
    print(f"README.md written  ·  issue {issue:03d}  ·  {total} merged upstream")

    # --- regenerate the plates with the live number baked into the hero ----
    subprocess.run([sys.executable, str(ROOT / "build" / "render.py"),
                    "--out", str(ROOT / "assets"), "--merged", str(total)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
