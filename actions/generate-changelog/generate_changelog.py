#!/usr/bin/env python3
"""Auto-generate a Keep a Changelog section from git history.

Extracts PR numbers from squash-merge commits, fetches actual PR titles via
the GitHub CLI, categorises them by conventional-commit prefix, updates
CHANGELOG.md in-place, and outputs the release-notes markdown.
"""

from __future__ import annotations

import os
import re
import subprocess  # nosec B404 -- only invoked with fixed arg lists, no shell
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_ORDER: list[str] = [
    "Breaking Changes",
    "Removed",
    "Deprecated",
    "Added",
    "Changed",
    "Fixed",
    "Security",
]

_TYPE_TO_CATEGORY: dict[str, str] = {
    "feat": "Added",
    "fix": "Fixed",
    "security": "Security",
    "deprecate": "Deprecated",
    "revert": "Removed",
}

_CC_REGEX = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\([^)]*\))?(?P<bang>!)?:\s*(?P<desc>.*)$",
)
_PR_NUMBER_REGEX = re.compile(r"\(#(\d+)\)$")
_SEMVER_TAG_REGEX = re.compile(r"^v?(\d+\.\d+\.\d+)$")
_PRE_RELEASE_REGEX = re.compile(r"(alpha|beta|rc)")
_SKIP_PATTERNS = re.compile(
    r"^Merge pull request"
    r"|^Merge branch"
    r"|^Merge remote"
    r"|^Prepare release"
    r"|^Create \d"
    r"|[Mm]erge.*to (main|master|workstation)"
    r"|[Mm]erge (main|master) to",
)
_BREAKING_REGEX = re.compile(r"\bBREAKING\b", re.IGNORECASE)
_TRAILING_PR_REGEX = re.compile(r"\s*\(#\d+\)$")

_CHANGELOG_HEADER = """\
<!-- markdownlint-disable MD024 -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
"""

_UNRELEASED_HEADING_REGEX = re.compile(r"^##\s+\[Unreleased\]", re.IGNORECASE)
_VERSION_HEADING_REGEX = re.compile(r"^##\s+\[.+\]")
_UNRELEASED_LINK_REGEX = re.compile(r"^\[unreleased\]:", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Runtime configuration built from environment variables."""

    version: str
    repo_url: str
    tag_prefix: str
    changelog_path: Path
    exclude_types: set[str]
    today: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class Entry:
    """A single changelog entry with its resolved category."""

    category: str
    text: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cmd(cmd: list[str]) -> str:
    """Run a subprocess and return stripped stdout, or empty string on failure."""
    result = (
        subprocess.run(  # nosec B603 -- only invoked with fixed arg lists, no shell
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    )
    return "" if result.returncode != 0 else result.stdout.strip()


def _map_category(cc_type: str, *, breaking: bool) -> str:
    """Map a conventional-commit type to a Keep a Changelog category."""
    if breaking:
        return "Breaking Changes"
    return _TYPE_TO_CATEGORY.get(cc_type, "Changed")


def _capitalise_first(text: str) -> str:
    """Uppercase the first character, leaving the rest unchanged."""
    return text[0].upper() + text[1:] if text else text


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def find_last_tag(tag_prefix: str) -> str | None:
    """Find the latest semver release tag, handling mixed v-prefix conventions."""
    raw_tags = _run_cmd(["git", "tag"]).splitlines()
    if not raw_tags:
        return None

    prefix_re = (
        re.compile(f"^{re.escape(tag_prefix)}") if tag_prefix else re.compile(r"^v?\d")
    )

    versions: list[tuple[tuple[int, ...], str]] = []
    for tag in raw_tags:
        if not prefix_re.search(tag):
            continue
        if not _SEMVER_TAG_REGEX.match(tag):
            continue
        if _PRE_RELEASE_REGEX.search(tag):
            continue
        stripped = tag.lstrip("v")
        parts = tuple(int(p) for p in stripped.split("."))
        versions.append((parts, tag))

    if not versions:
        return None

    versions.sort(key=lambda v: v[0], reverse=True)
    return versions[0][1]


def _fetch_pr_title(pr_number: str) -> str | None:
    """Fetch the actual PR title from GitHub via the ``gh`` CLI."""
    title = _run_cmd(
        ["gh", "pr", "view", pr_number, "--json", "title", "--jq", ".title"],
    )
    return title or None


def _parse_commit(title: str) -> tuple[str, bool, str]:
    """Parse a conventional-commit title into (type, breaking, description)."""
    cc_type = ""
    breaking = False
    description = title

    if cc_match := _CC_REGEX.match(description):
        cc_type = cc_match.group("type").lower()
        breaking = cc_match.group("bang") == "!"
        description = cc_match.group("desc")

    if _BREAKING_REGEX.search(description):
        breaking = True

    return cc_type, breaking, description


def _entry_from_commit(message: str, cfg: Config) -> Entry | None:
    """Convert a single commit message into a changelog Entry, or None to skip."""
    if _SKIP_PATTERNS.search(message):
        return None

    pr_match = _PR_NUMBER_REGEX.search(message)
    pr_number = pr_match.group(1) if pr_match else None

    title = message
    if pr_number:
        if pr_title := _fetch_pr_title(pr_number):
            title = pr_title

    cc_type, breaking, description = _parse_commit(title)

    if not breaking and cc_type and cc_type in cfg.exclude_types:
        return None

    category = _map_category(cc_type, breaking=breaking)
    description = _capitalise_first(description)
    description = _TRAILING_PR_REGEX.sub("", description)

    if pr_number:
        text = f"- {description} " f"([#{pr_number}]({cfg.repo_url}/pull/{pr_number}))"
    else:
        text = f"- {description}"

    return Entry(category=category, text=text)


def collect_entries(last_tag: str | None, cfg: Config) -> list[Entry]:
    """Walk git log from *last_tag* to HEAD and build categorised entries."""
    log_range = f"{last_tag}..HEAD" if last_tag else "HEAD"
    log_output = _run_cmd(
        ["git", "log", "--first-parent", "--pretty=format:%H %s", log_range],
    )
    if not log_output:
        return []

    entries: list[Entry] = []
    for line in log_output.splitlines():
        if not line.strip():
            continue
        _sha, message = line.split(" ", 1)
        if entry := _entry_from_commit(message, cfg):
            entries.append(entry)

    return entries


def build_section(entries: list[Entry]) -> str:
    """Render categorised entries as a Keep a Changelog markdown section."""
    lines: list[str] = []
    for category in CATEGORY_ORDER:
        cat_entries = [e.text for e in entries if e.category == category]
        if not cat_entries:
            continue
        lines.extend((f"### {category}", ""))
        lines.extend(cat_entries)
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Changelog file manipulation
# ---------------------------------------------------------------------------


def _ensure_changelog_exists(path: Path) -> None:
    """Create a skeleton Keep a Changelog file if one does not exist."""
    if path.is_file():
        return
    print(f"Warning: {path} not found, creating new file")
    path.write_text(_CHANGELOG_HEADER + "\n", encoding="utf-8")


def _insert_version_section(
    lines: list[str],
    new_section: str,
) -> list[str]:
    """Insert *new_section* after the ``[Unreleased]`` heading."""
    output: list[str] = []
    in_unreleased = False
    inserted = False

    for line in lines:
        stripped = line.rstrip("\n")

        if not in_unreleased and _UNRELEASED_HEADING_REGEX.match(stripped):
            in_unreleased = True
            output.append(line)
            continue

        if in_unreleased and not inserted:
            if _VERSION_HEADING_REGEX.match(stripped):
                output.extend(("\n", new_section + "\n", "\n", line))
                inserted = True
                continue
            output.append(line)
            continue

        output.append(line)

    if in_unreleased and not inserted:
        output.extend(("\n", new_section + "\n"))
    return output


def _update_comparison_links(
    lines: list[str],
    cfg: Config,
    last_tag: str | None,
) -> list[str]:
    """Rewrite the ``[unreleased]`` link and add a new version link."""
    output: list[str] = []
    updated = False

    for line in lines:
        if not updated and _UNRELEASED_LINK_REGEX.match(line):
            output.append(
                f"[unreleased]: {cfg.repo_url}/compare/{cfg.version}...HEAD\n",
            )
            if last_tag:
                output.append(
                    f"[{cfg.version}]: "
                    f"{cfg.repo_url}/compare/{last_tag}...{cfg.version}\n",
                )
            else:
                output.append(
                    f"[{cfg.version}]: " f"{cfg.repo_url}/releases/tag/{cfg.version}\n",
                )
            updated = True
        else:
            output.append(line)

    return output


def update_changelog(
    cfg: Config,
    section_body: str,
    last_tag: str | None,
) -> None:
    """Write the generated section into the changelog file."""
    path = cfg.changelog_path
    _ensure_changelog_exists(path)

    new_section = f"## [{cfg.version}] - {cfg.today}\n\n{section_body}"

    original = path.read_text(encoding="utf-8").splitlines(keepends=True)
    result = _insert_version_section(original, new_section)
    result = _update_comparison_links(result, cfg, last_tag)

    path.write_text("".join(result), encoding="utf-8")


# ---------------------------------------------------------------------------
# GitHub Actions output
# ---------------------------------------------------------------------------


def _write_github_output(name: str, value: str) -> None:
    """Append a multi-line output variable to ``$GITHUB_OUTPUT``."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as fh:
        fh.write(f"{name}<<CHANGELOG_EOF\n")
        fh.write(value + "\n")
        fh.write("CHANGELOG_EOF\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point -- reads config from environment variables."""
    version = os.environ.get("INPUT_VERSION")
    if not version:
        print("Error: INPUT_VERSION is required", file=sys.stderr)
        sys.exit(1)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    repo_url = (
        os.environ.get("INPUT_REPO_URL") or f"https://github.com/{repo}"
    ).rstrip("/")

    cfg = Config(
        version=version,
        repo_url=repo_url,
        tag_prefix=os.environ.get("INPUT_TAG_PREFIX", ""),
        changelog_path=Path(
            os.environ.get("INPUT_CHANGELOG_PATH", "CHANGELOG.md"),
        ),
        exclude_types={
            t.strip()
            for t in os.environ.get("INPUT_EXCLUDE_TYPES", "").split(",")
            if t.strip()
        },
    )

    print("::group::Generate Changelog")
    print(f"Version: {cfg.version}")
    print(f"Changelog: {cfg.changelog_path}")
    print(f"Repo URL: {cfg.repo_url}")

    last_tag = find_last_tag(cfg.tag_prefix)
    if last_tag:
        print(f"Last release tag: {last_tag}")
    else:
        print("No previous release tag found, including all commits")

    entries = collect_entries(last_tag, cfg)

    if not entries:
        print(
            f"No changelog entries found between "
            f"{last_tag or 'beginning'} and HEAD",
        )
        print("::endgroup::")
        _write_github_output("release-notes", "No notable changes.")
        return

    section_body = build_section(entries)

    print("\nGenerated changelog section:\n---")
    print(f"## [{cfg.version}] - {cfg.today}\n")
    print(section_body)
    print("---")

    update_changelog(cfg, section_body, last_tag)
    print(f"Updated {cfg.changelog_path}")

    _write_github_output("release-notes", section_body)
    print("::endgroup::")


if __name__ == "__main__":
    main()
