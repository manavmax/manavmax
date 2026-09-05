#!/usr/bin/env python3
"""Rewrite the live regions of README.md, regenerate the graphics, then check them.

Two regions are owned by this script, each delimited by a matched pair of HTML
comments so the rest of the file is never touched:

    <!-- dateline:start -->  ... <!-- dateline:end -->
    <!-- upstream:start -->  ... <!-- upstream:end -->

The merged-PR counts come from the GitHub Search API, which returns a
`total_count` for a query -- so one request per repository answers the question
with no pagination at all.

Safety rail: the count for a repository is never allowed to go DOWN. Merged PRs
do not un-merge, so a decrease means the API answered wrong, not that history
changed -- an HTTP 403, a rate-limit, or a token that cannot see the repository.
The first version of this rail only caught `None` and an exact 0, so a partial
answer that undercounted sailed straight through and the published page quietly
lost merges. Any decrease now keeps the previous number and shouts on stderr.

If the counts read low in CI, the likely cause is the token: `secrets.GITHUB_TOKEN`
is scoped to THIS repository, and the Search API can answer conservatively for
repositories it has no read context on. A user PAT with `public_repo`, stored as a
secret and passed as GH_TOKEN, is the fix. Nothing here can tell which figure is
correct on its own; it can only refuse to publish the smaller one.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

USER = "manavmax"
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
        n, was = merged_prs(repo), prior.get(repo, 0)
        if n is None:
            n, why = was, "no answer"
        elif n < was:
            n, why = was, f"API said {n}, previously {was}"
        else:
            why = ""
        if why:
            degraded.append((repo, why))
        counts[repo] = n
        print(f"  {repo:32s} {n:3d}{'  (kept previous: ' + why + ')' if why else ''}")

    total = sum(counts.values())
    for repo, why in degraded:
        print(f"  ! {repo}: kept previous count -- {why}", file=sys.stderr)
    if degraded:
        print("  ! a merged PR cannot un-merge. If this persists, pass a user PAT "
              "with public_repo scope as GH_TOKEN instead of secrets.GITHUB_TOKEN.",
              file=sys.stderr)

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
        f"counted on <code>{today:%Y-%m-%d}</code></samp>",
    ]
    md = replace(md, "upstream", "\n".join(rows) + "\n")

    # --- regenerate the plates with the live number baked into the masthead ---
    subprocess.run([sys.executable, str(ROOT / "build" / "render.py"),
                    "--out", str(ROOT / "assets"), "--merged", str(total)], check=True)
    sys.path.insert(0, str(ROOT / "build"))
    # From source, not from a .pyc: CPython accepts a cache whose recorded
    # (mtime_seconds, size) match the source, and swapping one hex literal for
    # another changes neither. See the same guard at the top of build/verify.py.
    sys.dont_write_bytecode = True
    shutil.rmtree(ROOT / "build" / "__pycache__", ignore_errors=True)
    import render                       # for the plate count only; not to draw
    plates = len(render.PLATES) * len(render.T)

    # --- region 2: the dateline -------------------------------------------
    # <code> rather than backticks: this block sits inside <div align="center">,
    # where GitHub does not run inline markdown, so backticks render as literal
    # quote marks. That shipped once. It is why these are explicit tags.
    md = replace(md, "dateline",
                 f"<code>SESSION {today:%Y-%m-%d}</code> · <code>PLATES {plates}</code>"
                 " · <code>RENDER build/render.py</code>"
                 " · <code>CHECK build/verify.py</code> · <code>JS 0</code>")

    README.write_text(md, encoding="utf-8")
    print(f"README.md written  ·  {plates} plates  ·  {total} merged upstream")

    # --- refuse to publish a page that does not pass the geometry check ------
    subprocess.run([sys.executable, str(ROOT / "build" / "verify.py")],
                   check=True, cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
