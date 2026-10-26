#!/usr/bin/env python3
"""Print the version of the newest stable release older than VERSION, or nothing.

Usage:
  gh release list --json tagName,isPrerelease,isDraft --limit 1000 | previous_release.py VERSION

Tags may carry a leading "v"; the printed version never does. Pre-releases and drafts are
skipped, so "change since" always compares against what consumers last got as stable.
"""

import json
import re
import sys
from typing import Optional, Tuple

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(.+))?$")


def parse(tag: str) -> Optional[Tuple[int, int, int]]:
    """(major, minor, patch) of a stable semver tag; None for anything else."""
    match = SEMVER.match(tag)
    if not match or match.group(4):
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def previous(releases: list, version: str) -> Optional[str]:
    """Newest stable, non-draft release version strictly older than version."""
    current = parse(version)
    if current is None:
        return None
    older = []
    for release in releases:
        if release.get("isDraft") or release.get("isPrerelease"):
            continue
        parsed = parse(release.get("tagName", ""))
        if parsed is not None and parsed < current:
            older.append(parsed)
    if not older:
        return None
    return ".".join(str(part) for part in max(older))


def main(argv: list) -> int:
    """Read gh release JSON from stdin and print the previous version."""
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    found = previous(json.load(sys.stdin), argv[0])
    if found:
        print(found)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
