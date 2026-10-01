#!/usr/bin/env python3
"""Render the "App size impact" section of a release body from measure.sh output.

Usage:
  render_release_size.py --platform android|ios --version V [--previous P]
      --results-dir DIR --row ID=LABEL [--row ...] [--method-url URL]

Each row reads DIR/<id>-<version>.json (and DIR/<id>-<previous>.json for the change column).
--new ID marks a package the previous release did not have, so its change reads as new.
A missing or unparsable file renders as "not measured", never as a zero.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

START = "<!-- size-impact:start -->"
END = "<!-- size-impact:end -->"

# (metric key, column heading). The first metric also drives the "change" column.
METRICS = {
    "android": (
        ("apk_bytes", "APK size"),
        ("download_bytes", "Download size"),
        ("dex_bytes", "Code (dex)"),
    ),
    "ios": (
        ("app_bundle_bytes", "App bundle"),
        ("executable_bytes", "Executable"),
    ),
}

STARTING_APP = {
    "android": "a minified release APK, on top of a Compose + Material3 starting app",
    "ios": "a release build of an empty SwiftUI app",
}


def load(path: Path) -> Optional[dict]:
    """Read one measure.sh result; None when it is missing or empty."""
    try:
        text = path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else None
    except (OSError, ValueError):
        return None


def impact(data: Optional[dict], metric: str) -> Optional[int]:
    """Bytes the package adds for one metric: with minus baseline."""
    if data is None:
        return None
    try:
        values = data["metrics"][metric]
        return int(values["with"]) - int(values["baseline"])
    except (KeyError, TypeError, ValueError):
        return None


def human(size: Optional[int]) -> str:
    """Format a byte count, or "not measured" for None."""
    if size is None:
        return "not measured"
    sign = "-" if size < 0 else ""
    size = abs(size)
    for unit, scale in (("MB", 1024 * 1024), ("KB", 1024)):
        if size >= scale:
            return f"{sign}{size / scale:.2f} {unit}"
    return f"{sign}{size} bytes"


def change(now: Optional[int], was: Optional[int]) -> str:
    """Signed difference between this release's impact and the previous one's."""
    if now is None or was is None:
        return "not measured"
    difference = now - was
    if difference == 0:
        return "no change"
    return ("+" if difference > 0 else "") + human(difference)


def render(args: argparse.Namespace) -> str:
    """Build the marker-delimited markdown section."""
    metrics = METRICS[args.platform]
    results = Path(args.results_dir)
    header = ["Package", *(label for _, label in metrics)]
    if args.previous:
        header.append(f"Change since {args.previous}")
    rows = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    toolchains = set()
    for row in args.row:
        package, _, label = row.partition("=")
        now = load(results / f"{package}-{args.version}.json")
        if now and now.get("toolchain"):
            toolchains.add(now["toolchain"])
        cells = [label or package, *(human(impact(now, key)) for key, _ in metrics)]
        if args.previous and package in (args.new or []):
            cells.append("new in this release")
        elif args.previous:
            was = load(results / f"{package}-{args.previous}.json")
            first = metrics[0][0]
            cells.append(change(impact(now, first), impact(was, first)))
        rows.append("| " + " | ".join(cells) + " |")

    method = f"Measured from the published {args.version} artifacts"
    if toolchains:
        method += " with " + "; ".join(sorted(toolchains))
    method += "."
    if args.method_url:
        method += f" [How this is measured]({args.method_url})."
    return "\n".join(
        [
            START,
            "## App size impact",
            "",
            f"What this release adds to {STARTING_APP[args.platform]}.",
            "",
            *rows,
            "",
            f"<sub>{method}</sub>",
            END,
        ]
    )


def main() -> int:
    """Parse arguments and print the section."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--platform", required=True, choices=sorted(METRICS))
    parser.add_argument("--version", required=True)
    parser.add_argument("--previous")
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--row", required=True, action="append", help="ID=LABEL")
    parser.add_argument("--method-url")
    parser.add_argument(
        "--new",
        action="append",
        help="ID of a package the previous release did not have",
    )
    print(render(parser.parse_args()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
