#!/usr/bin/env python3
"""Replace the size-impact section of a release body, or append it, and print the new body.

Usage:
  update_release_body.py <body-file> <section-file>

Only the text between the size-impact markers is ever replaced, so the release notes around it
are untouched and running this twice gives the same body.
"""

import sys
from pathlib import Path

START = "<!-- size-impact:start -->"
END = "<!-- size-impact:end -->"


def update(body: str, section: str) -> str:
    """Return body with its size-impact section replaced, or with section appended."""
    section = section.strip()
    start = body.find(START)
    end = body.find(END, start + len(START)) if start != -1 else -1
    if start != -1 and end != -1:
        return body[:start] + section + body[end + len(END) :]
    if start != -1:
        # A start marker with no end would make the replacement swallow the rest of the body.
        raise ValueError(
            "release body has a size-impact start marker but no end marker"
        )
    stripped = body.rstrip()
    return f"{stripped}\n\n{section}\n" if stripped else f"{section}\n"


def main(argv: list) -> int:
    """Read the two files and print the updated body."""
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    body = Path(argv[0]).read_text(encoding="utf-8")
    section = Path(argv[1]).read_text(encoding="utf-8")
    try:
        sys.stdout.write(update(body, section))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
