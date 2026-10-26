#!/usr/bin/env python3
"""Print the `<package id>=<label>` rows a product's release VERSION reports, one per line.

Usage:
  rows.py PRODUCT VERSION

PRODUCT is a key of repos.json.

A row whose package was first published after VERSION is left out.
"""

import json
import sys
from pathlib import Path
from typing import List

from previous_release import parse

HERE = Path(__file__).resolve().parent


def rows_for(product: str, version: str) -> List[str]:
    """The rows of repos.json for product that apply to version."""
    entry = json.loads((HERE / "repos.json").read_text(encoding="utf-8"))[product]
    current = parse(version.split("-")[0])
    rows = []
    for package, label, *since in entry["rows"]:
        first = parse(since[0]) if since else None
        if first is not None and current is not None and current < first:
            continue
        rows.append(f"{package}={label}")
    return rows


def main(argv: list) -> int:
    """Print the rows for PRODUCT VERSION."""
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print("\n".join(rows_for(argv[0], argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
